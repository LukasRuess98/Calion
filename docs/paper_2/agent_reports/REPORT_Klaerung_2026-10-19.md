# REPORT — Klärung und Datenbeschaffung, Paper 2 (Stand 2026-10-19)

Antwort auf den Agent-Auftrag v4 vom 2026-10-19. Stufe 1 (nur Lesen/Rechnen, kein Solve,
keine Codeänderung, keine Überschreibung bestehender Ergebnisdateien). Jede Aussage ist
als **belegt** (aus Datei/Log gelesen), **berechnet** (aus belegten Werten abgeleitet) oder
**vermutet** gekennzeichnet.

---

## WICHTIG — Branch-Hinweis (zuerst lesen)

Diese gesamte Prüfung lief gegen den Code-Stand des `main`-Branches (dort, wo dieser Report laut Auftrag auch
hin committet wird). Das Zusatz-Abbildungsprogramm, der Z4-Validierungsfix, der Preisspreizungs-Mechanismus und die
12 SPREIZ/VERMARKT2-Z3-Szenarien aus einer PARALLELEN, in dieser Woche abgeschlossenen Arbeitssession liegen
**ausschließlich auf dem separaten, bereits gepushten Branch `Loc_TES_Study_P2`**
(`https://github.com/LukasRuess98/Calion.git`, Commit `cee960b`) — NICHT auf `main`. Konkret fehlen auf `main`:
- Der Z4-Fix in `scripts/paper/extract_artefacts.py`/`tools/validation_stadtbach.py` (die Schließungsformel auf
  `main` ist die ALTE, verlustfreie Version — `grep` bestätigt: Zeile 977 auf `main` lautet
  `closure_err_pct = abs(supply - dump - demand) / demand * 100`, OHNE `- losses`).
- `site.price_amplitude_factor` in `calion/io/loader.py` (0 Treffer auf `main`).
- Die Szenario-Definitionen `SB-S1-HK0{,-PIN0}-{SPREIZ15,SPREIZ20,VERMARKT2}` + MM-Äquivalente in `scenarios.yaml`
  (0 Treffer auf `main`).
- §4ck bis §4cp in `MODEL_AND_DOE_CONTROL.md` (das Dokument endet auf `main` bei §4cj — **H7 ist für `main` korrekt**,
  aber NICHT für den Stand der tatsächlich geleisteten Arbeit, die auf dem Feature-Branch dokumentiert ist).

**Alle in diesem Report zitierten `output/`-Ergebnisdateien (meta.json, dispatch_hourly.csv, cost_breakdown.json,
Gurobi-Logs) sind davon NICHT betroffen** (`output/` ist gitignored, unabhängig vom Branch auf der Platte vorhanden,
alle Zahlen in diesem Report sind echte, bereits abgeschlossene Lauf-Ergebnisse). Betroffen sind NUR Verweise auf den
aktuellen CODE-Stand (markiert, wo relevant, insbesondere A5). **Empfehlung:** vor Verlass auf den Z4-Fix oder die
Preisspreizungs-Ergebnisse diesen Report (`main`) gegen `Loc_TES_Study_P2` abgleichen, oder den Branch nach `main`
mergen — das liegt außerhalb des "nur Lesen"-Auftrags dieser Prüfung, wird hier nur gemeldet.

**AKTUALISIERUNG, unmittelbar vor Abgabe dieses Reports (2026-10-19, ca. 15:30):** `main`s Arbeitsverzeichnis wird
offenbar GERADE PARALLEL von einem anderen Prozess verändert — `scripts/paper_2/ac_run.sh` und
`backfill_closure_ac3.py` sind neue, unversionierte Dateien (Änderungszeit 15:26/15:28, während dieser Report
geschrieben wurde), und `scripts/paper/extract_artefacts.py`s Schließungsformel enthält JETZT bereits `- losses`
(Zeile 984: `closure_err_pct = abs(supply - dump - losses - demand) / demand * 100`) — anders als beim ersten Check
weiter oben (damals ohne `- losses`, Zeile 977). **Der oben beschriebene Branch-Unterschied bei A5 ist damit
möglicherweise bereits teilweise überholt** — vermutlich hat der Auftraggeber selbst (oder ein paralleler Agent-Lauf)
in der Zwischenzeit einen eigenen, unabhängigen Fix auf `main` angewendet. Dieser Report wurde NICHT mehr komplett
gegen diesen neuesten Stand nachgezogen (Zeitdruck) — **A5s Aussagen zum Code-Stand von `main` vor dieser Aktualisierung
lesen, nicht als letzten Stand.** Die `output/`-Zahlen in A5(b) (0,269 % für SB-S2/S3) bleiben davon unberührt korrekt
(eigene Berechnung, nicht vom Produktionscode abhängig).

---

## Widersprüche zu §1

- **H2 ist nur TEILWEISE korrekt.** `peak_import_MW = 1,0000` gilt für `sb_pin0_monthly`,
  `mm_pin0_monthly`, `mm_free_monthly` (**belegt**, `economics.csv`), aber **NICHT** für
  `sb_free_monthly` (SB-S1-HK0-MONTHLY, frei): dort steht `peak_import_MW = 0,4120841196738621`
  — ein plausibler, realer Wert. Siehe A1(d) für die Ursache und warum die Inkonsistenz
  selbst ein Indiz ist, kein Zufall.
- **H7 ist für den `main`-Branch korrekt, aber nicht für den tatsächlichen Arbeitsstand** — siehe Branch-Hinweis oben.
  §4ck-§4cp existieren bereits, nur auf einem anderen Branch.

(Keine weiteren Widersprüche zu §1 gefunden; H1, H3, H4, H5, H6 decken sich mit dem,
was unten belegt/berechnet wurde — Details je Frage.)

---

## Block A — Verifikation der Auffälligkeiten

### A1 — MONTHLY (Monatsleistungspreis)

**A1(a) — ist der Monatsleistungspreis im freien Modell strukturell aktiv?**
Antwort: **Ja, belegt.** Build-Diff (aus `meta.json`, kein neuer Solve nötig):

| Lauf | n_vars | n_constraints | Δ vs. Jahres-Variante |
|---|---|---|---|
| SB-S1-HK0 (Jahr) | 7.358.422 | 9.224.291 | — |
| SB-S1-HK0-MONTHLY (frei) | 7.358.434 | 9.233.051 | **+12 Vars, +8.760 Constraints** |
| MM-S1-HK0 (Jahr) | 4.599.021 | 4.940.651 | — |
| MM-S1-HK0-MONTHLY (frei) | 4.599.033 | 4.949.411 | **+12 Vars, +8.760 Constraints** |

Evidenz: `output/v7_final/SB-S1-HK0/meta.json` (n_vars/n_constraints), `output/_z3/sb_free_monthly/paper2_runs/SB-S1-HK0-MONTHLY/meta.json`,
analog für MM. +12 = `model.P_buy_peak_month` (12 Monate), +8.760 = `peak_con_month` (eine Constraint je Stunde des Jahres,
`calion/models/constraint_builder.py`, `add_grid_market_constraints(..., month_groups=...)`). Stimmt exakt mit der Y3-Mechanismus-Beschreibung
überein (`calion/models/model_finalizer.py:662-675`).

**A1(b) — Gurobi-Log, MIP-Start, Inkumbenten.**
Antwort: **belegt.** `output/_z3/sb_free_monthly/logs/gurobi_SB-S1-HK0-MONTHLY.log`: MIP-Start aus `output/v7_final/SB-S1-HK0`
übernommen (`MIP start: warmstart_from=output/v7_final/SB-S1-HK0`, scenario_runner-Log), `Solution count 1` im finalen
Gurobi-Abschluss — über die vollen 8h (28.800s TimeLimit, `maxTimeLimit` erreicht bei Gap 0,1828%) wurde **keine** gegenüber
dem Warmstart verbesserte Lösung gefunden. Letzte Verbesserung = der Warmstart selbst (keine neue Inkumbente danach).

**A1(c) — Woher kommt `cost_demand_charge_eur`?**
Antwort: **belegt.** Zwei unabhängige Pfade geprüft, beide zeigen denselben (nahezu identischen) Wert:
- `economics.csv` (`scripts/paper/extract_artefacts.py`): `cost_demand_charge_eur` wird NICHT direkt aus `P_buy_peak_month`
  berechnet, sondern aus dem extrahierten `obj`-Dict übernommen (Pfad nicht weiter verfolgt, da Ergebnis mit `cost_breakdown.json`
  übereinstimmt).
- `cost_breakdown.json` (`calion/run/result_collector.py`): `Demand_charge_cost_EUR` liest laut früherer Dokumentation
  (docs SS4cb/Y3) die LIVE Objective-Expression (`_diag_demand_cost_expr`), die bei `demand_charge_mode=monthly` auf
  `calculate_demand_charge_monthly()` zeigt (`calion/models/model_finalizer.py:743-747`).

Beide Pfade liefern **52.433,58322 EUR** (frei, monatlich) vs. **52.433,58339 EUR** (frei, jährlich) — Differenz 0,00017 EUR,
numerisches Rauschen, kein struktureller Unterschied.

**Grund (berechnet, aus `dispatch_hourly.csv`, echte Stundenwerte, nicht aus Zusammenfassung):**
`P_buy_MW`-Monatsmaxima in `output/_z3/sb_free_monthly/paper2_runs/SB-S1-HK0-MONTHLY/dispatch_hourly.csv`:

```
Monat  1 ..12: je 0,412084 MW (IDENTISCH in allen 12 Monaten)
Jahresmaximum: 0,4120841196738634 MW
Summe(Monatsmaxima × 10.603,3333)  = 52.433,58 EUR
Jahresmaximum × 127.240            = 52.433,58 EUR
```
Weil der monatliche Spitzenwert in JEDEM der 12 Monate exakt denselben Wert erreicht (der freie Investitions-Fall hält den
Netzbezug ganzjährig auf einem konstanten Deckel), ist `Σ(Monatsmaxima)×Monatssatz` durch Konstruktion identisch zu
`Jahresmaximum×Jahressatz` (12×10.603,3333 = 127.240,00 exakt). **Kein Bug, ein reales Dispatch-Resultat** — bereits in
`MODEL_AND_DOE_CONTROL.md` §4co (13.10., nur auf `Loc_TES_Study_P2`, siehe Branch-Hinweis) als Nebenbefund dokumentiert,
hier mit frischer, unabhängiger Stundenwert-Rechnung bestätigt statt nur zitiert.

Bei PIN0 (kein Investitionsspielraum, Bestand folgt der realen Lastkurve mit echten saisonalen Spitzen) tritt der Effekt
NICHT auf: PIN0-MONTHLY `cost_demand_charge_eur = 23.493,84` EUR (deutlich kleiner als S1-frei) — **offen**, ein direkter
Vergleich gegen PIN0-Jahr wurde nicht neu nachgerechnet (die 22.487-EUR-Ersparnis aus §4ce wurde an einem anderen,
S0-statt-S1, älteren Lauf gezeigt, **vermutet** hier übertragbar).

**Fazit A1:** Intervall für SB-MONTHLY (frei) ist **gültig** — der Nahezu-Null-Unterschied zur Jahresabrechnung ist ein reales
Dispatch-Resultat (Lastglättung durch Investitionsfreiheit), kein Extraktionsfehler. Die Y1-Intervall-Rechnung selbst
(PIN0 vs. frei, beide unter demselben Monatsmodus) bleibt davon unberührt korrekt.

**A1(d) — Woher kommt `peak_import_MW = 1,0`?**
Antwort: **belegt (Fundort), Ursache strukturell plausibel, nicht abschließend bewiesen.**
`scripts/paper/extract_artefacts.py:211`: `peak_import = _safe(obj.get("P_buy_peak_MW"))` — liest die **jährliche**
`model.P_buy_peak`-Variable, NICHT `P_buy_peak_month`. Unter `demand_charge_mode=monthly` steuert laut
`model_finalizer.py:743` die Objective-Auswahl auf `P_buy_peak_month` um — die alte `P_buy_peak`-Variable bleibt strukturell
im Modell (Constraint `P_buy[t] <= P_buy_peak` existiert vermutlich weiterhin unverändert), hat aber **keinen Kostendruck
mehr**, der sie auf ihr tatsächliches Minimum drückt. Sie ist dadurch bei fehlendem Zielfunktionsbezug frei bis auf die
reine Erfüllbarkeits-Untergrenze, und Gurobi kann sie auf jeden erfüllbaren Wert setzen.

Stichprobe (`economics.csv`, 4 Monats-Läufe, **belegt**):

| Lauf | `peak_import_MW` |
|---|---|
| sb_pin0_monthly | 1,0 |
| mm_pin0_monthly | 1,0 |
| mm_free_monthly | 1,0 |
| sb_free_monthly | 0,412084 (einzige Ausnahme) |

`_safe()` (Zeile 70-75) hat Default 0,0, nicht 1,0 — die "1,0" ist also ein echter gespeicherter Wert aus dem Modell, kein
Extraktions-Fallback. Warum ausgerechnet SB-free von der 1,0 abweicht und einen plausiblen Wert zeigt, wurde NICHT
abschließend geklärt (**offen** — würde einen Blick auf die tatsächliche `P_buy_peak`-Variablenbindung/-Bounds in
`system_builder.py`/`model_finalizer.py` brauchen, die in Stufe 1 nicht mit Solver-internen Werten über den reinen
Build-Diff hinaus geprüft wurde).

**Meldepflicht A1-M1:** `peak_import_MW` in `economics.csv` ist unter `demand_charge_mode=monthly` nicht belastbar
(zeigt einen wahrscheinlich bedeutungslosen Platzhalterwert, meist 1,0). Betrifft alle 4 geprüften Monats-Läufe (PIN0 SB,
PIN0 MM, frei MM; frei SB zufällig unauffällig). Fixvorschlag: in `extract_artefacts.py` bei `demand_charge_mode=monthly`
stattdessen `max(P_buy_peak_month[*])` oder das echte `dispatch_hourly.csv`-Spaltenmaximum verwenden. Aufwand: klein
(~15 Zeilen, ein Re-Extraktions-Lauf pro betroffenem Verzeichnis, kein Solve nötig).

### A2 — SB-S2 = SB-S3

**A2(a) — MIP-Start, Inkumbentenverlauf, je eine build=1-Lösung gefunden?**
Antwort: **belegt.** `output/logs/gurobi_SB-S2-HK0.log` (Block ab Zeile 4355, "Fri Oct 2 15:49:01") und
`gurobi_SB-S3-HK0.log` (Block ab Zeile 2188, "Sat Oct 3 00:01:52") — beide identisch im Muster:
```
Processing user MIP start: 0 nodes explored in subMIP, total elapsed time 6s
User MIP start produced solution with objective 2.33843e+07 (7.70-7.74s)
Loaded user MIP start with objective 2.33843e+07
...
Solution count 1: 2.33843e+07
Time limit reached
```
**`Solution count 1` in BEIDEN Läufen** — über die vollen 8h (28.800s, `MIPFocus=3`) wurde in keinem der beiden Läufe
eine gegenüber dem MIP-Start verbesserte Lösung gefunden. Es wurde **zu keinem Zeitpunkt** eine `build=1`-Lösung
gefunden oder auch nur zwischenzeitlich exploriert (kein zweiter Inkumbent, der das zeigen könnte). Exakt dasselbe
Muster wie bei den AA3-Läufen c0×1,3/×1,5 (`MODEL_AND_DOE_CONTROL.md` §4ck, nur auf `Loc_TES_Study_P2`) — **dieselbe
Einschränkung gilt hier:** S2/S3s "kein Speicher"-Ergebnis ist eine valide OBERE Schranke relativ zum MIP-Start, nicht
zwingend das global optimale Re-Design. Der MIP-Start-Zielwert (23.3843 Mio.) entspricht fast exakt dem alten,
warmstart-liefernden SB-S0-HK0-Wert (§4cf) — der Start selbst hatte bereits `build=0` codiert, der Solver musste diese
Entscheidung nie in Frage stellen.

**A2(b) — Warum ist S3 bit-identisch zu S2?**
Antwort: **belegt.** `geometry.csv` beider Läufe: `build=0, V_TES_m3=0.0` (identisch). Der einzige Konfigurationsunterschied
zwischen S2 und S3 ist `hot_charging: true` (`configs/paper_2/scenarios.yaml`) — ein Flag, das nur die
Ladetemperatur-Obergrenze eines TATSÄCHLICH gebauten Tanks betrifft. Da in beiden Läufen `build=0` gilt, hat das Flag
keinen Angriffspunkt im Modell → identische Dispatch-/Kostenwerte sind die logisch zwingende Folge, kein Zufall.

**A2(c) — Build-only-Diff S1 vs. S2 (investierbar); physikalische Anschließbarkeit an j_man.**
Antwort: **belegt (n_vars/n_constraints aus echten, bereits gebauten/gelösten Modellen — kein neuer Build nötig, da
diese Zahlen modellgrößenbestimmt und lösungsunabhängig sind):**

| Lauf | n_vars | n_constraints |
|---|---|---|
| SB-S1-HK0 | 7.358.422 | 9.224.291 |
| SB-S2-HK0 | 7.358.422 | 9.224.291 (**bit-identisch zu S1**) |
| SB-S3-HK0 | 7.367.182 | 9.233.051 (**+8.760 ggü. S1/S2 — durch `hot_charging`**) |

S1 und S2 sind strukturell gleich groß — kein Hinweis auf eine andere Knotenbilanz-FORM durch die TES-Kandidatenplatzierung
(anders als bei AB1s PIN0-Fall war hier KEIN Unterschied zu erwarten, da beide Läufe volle Investitionsfreiheit haben;
gleiche Variablen-/Constraint-ZAHL ist ein starkes, aber kein vollständiges Indiz — gleiche Anzahl beweist nicht
zwingend identische Constraint-Inhalte, nur identische Kardinalität). S3 hat **+8.760 Constraints/Vars gegenüber
S1/S2** — exakt ein Term je Stunde des Jahres, strukturell plausibel einer `hot_charging`-spezifischen
Lade-Temperatur-Constraint zuzuordnen (nicht im Code verifiziert, **vermutet** aus der Magnitude).

**Physikalische Anschließbarkeit (berechnet, Pfeifenkapazität, keine Solver-Daten nötig):** `j_man` hat in
`configs/paper_2/Stadtbach_topo.yaml` **genau eine** Rohrverbindung (`hkw_to_man`, Zeile 345-351: `from: j_hkw,
to: j_man, diameter_mm: 400`). Mit `max_velocity_m_s=3.0` (Standardannahme dieses Projekts, siehe BC-SB-Logs) und
ΔT=35K: Querschnitt 0,1257 m², Massenstrom 366,1 kg/s, **thermische Maximalleistung ≈ 53,7 MW**. S1s Tank hat
`cap_power_MW = 109,5` (E/4h-Regel auf 438 MWh) — **mehr als doppelt so viel** wie die einzige Leitung nach j_man
tragen könnte. **Fazit (berechnet, nicht modellseitig verifiziert):** ein S1-großer Tank an j_man wäre an der
hydraulischen Anbindung (nicht nur wirtschaftlich) eng limitiert — j_man ist im Modell ein Sackgassen-Knoten, keine
Durchgangsstation.

**A2(d) — Wäre S2 mit dem S1-Tank (438 MWh) überhaupt zulässig lösbar?**
Antwort: **vermutet (Einschätzung, kein Lauf, wie angefordert).** Gegeben A2(c)s Rohrkapazitäts-Rechnung (~54 MW an
der einzigen Leitung) wäre ein Tank mit `cap_power_MW=109,5` wie bei S1 an j_man **wahrscheinlich NICHT ohne
Modellanpassung zulässig** (Pipe-Geschwindigkeitsconstraint würde vermutlich verletzt, sofern die maximale
Lade-/Entladeleistung voll genutzt werden müsste) — ODER der Solver würde den Tank selbst kleiner dimensionieren
(E/4h ist eine Auslegungsheuristik, keine harte Bindung an 438 MWh) und könnte dadurch innerhalb der Rohrgrenze
bleiben, nur mit entsprechend geringerem `cap_power_MW`. Ohne echten Lauf nicht abschließend zu klären.

**Meldepflicht A2-M1:** SB-S2/S3s "kein Speicher"-Befund hat dieselbe Stuck-Warmstart-Einschränkung wie AA3s c0×1,3/×1,5
(`Solution count 1` über volle 8h). Betroffen: beide SB-S2-HK0 und SB-S3-HK0 (v7_final). Fixvorschlag: Re-Solve mit
S1s Lösung als MIP-Start (statt dem alten S0-Wert) ODER ohne Warmstart, um zu prüfen, ob der Solver eigenständig
`build=0` bestätigt oder eine andere Größe findet. Aufwand: siehe C2(i).

### A3 — c0-Sweep

**A3(a) — Inkumbentenverlauf, Warmstartquelle, Tankgröße je Lauf verändert?**
Antwort: **belegt** (frisch verifiziert, nicht aus Gedächtnis zitiert): alle drei 48h-Läufe warmstarten aus
**derselben** Quelle `output/v7_final/SB-S1-HK0` (c0×1,0-Basislauf), NICHT voneinander verkettet:

| Lauf | Warmstart | Solution count | Tankgröße |
|---|---|---|---|
| c0×1,3 | `output/v7_final/SB-S1-HK0` | **1** (nie verbessert) | 30.379,4 m³ (= wie c0×1,0) |
| c0×1,5 | `output/v7_final/SB-S1-HK0` | **1** (nie verbessert) | 30.379,4 m³ (= wie c0×1,0) |
| c0×2,0 | `output/v7_final/SB-S1-HK0` | **10** (mehrfach verbessert) | 2.566,3 m³ (eigenständig gefunden) |

Evidenz: `output/_parallel_aa3/{c0x1.3,c0x1.5,c0x2.0}/chain.output:18` (warmstart_from-Zeile),
`.../logs/gurobi_SB-S1-HK0.log` (Solution-count-Zeile). Deckt sich mit §4ck — hier erneut aus den Rohlogs bestätigt.

**A3(b) — Konsistenz-Assertion Tankkosten im Objective.**
Antwort: **berechnet**, mit einer offenen Lücke. Formel (`calion/models/blocks/geometric_storage.py:377-388`,
N=1 Tank bestätigt da V≤unit_tank_m3=50.000 in allen Sweep-Punkten): `Kosten_raw = c0_eur·mult·(V/v0)^b`.

| Lauf | V [m³] | c0_scaled [EUR] | Kosten_raw [EUR] (berechnet) |
|---|---|---|---|
| c0×1,0 | 30.379,4 | 2.500.000 | 5.441.835,92 |
| c0×1,3 | 30.379,4 | 3.250.000 | 7.074.386,70 |
| c0×1,5 | 30.379,4 | 3.750.000 | 8.162.753,88 |
| c0×2,0 | 2.566,3 | 5.000.000 | 1.929.679,58 |

Plausibilitätsprobe c0×1,0→c0×1,3 (V unverändert, nur reiner Kosten-Durchgriff erwartet): Δ Kosten_raw = 1.632.550,78 EUR,
annuitätisch (`annual_factor=0,0651` für `tes_sb`, aus Build-Log) = **106.279,06 EUR/a vorhergesagt**. Tatsächliches
ΔTAC (c0×1,3 − c0×1,0, aus `meta.json obj_eur`) = **114.362,52 EUR/a**. Residuum 8.083,47 EUR/a (7,6 % des
vorhergesagten Werts) — **nicht auf den Euro rekonziliert.** `full_solution_dump.json` enthält nur Variablenwerte,
keine Expressions wie `tes_sb_capex_raw` (`grep` nach dem Expressionsnamen: 0 Treffer) — eine exakte Live-Werte-Probe
war in Stufe 1 ohne Solve/Re-Extraktion nicht möglich. **Offen:** Ursache des 7,6-%-Residuums (Gap-Rauschen zwischen
unabhängig gelösten Läufen am wahrscheinlichsten, da keiner der Läufe exakt 0 % Gap hat — nicht bewiesen).

**A3(c) — c0×0,5/×0,7: Pfad und Kettenstatus.**
Antwort: **belegt, mit Einschränkung zur Pfad-Dauerhaftigkeit.** Beide Punkte haben **kein Export-Verzeichnis**
(Absturz vor Extraktion) — einzige Evidenz liegt in Task-Log-Dateien unter dem lokalen Windows-Temp-Pfad dieser
Session, NICHT unter `output/` oder einem stabilen Server-Pfad:
`C:\Users\LKR\AppData\Local\Temp\3\claude\...\tasks\z_sb_s1_sweep_chain_resume2.output` (Änderungsdatum 2026-10-09
08:46). Zeile 1663: `SB-S1-SWEEP-RESULT[c0x0.5]: {'status': 'error_solve', 'error': 'Out of memory', 'solve_s': 151836.78}`.
**Warnung:** dieser Temp-Pfad ist sessiongebunden und kann bei System-Bereinigung verschwinden — nicht als dauerhafte
Quelle geeignet. Kettenstatus: **beendet, nicht fertig** — c0×0,5 Out-of-Memory nach ~42,2h, c0×0,7 von derselben Kette
automatisch fortgesetzt und später auf Anweisung kontrolliert beendet (ebenfalls kein Export). Rohe Log-Werte (aus
Gurobi-B&B-Tabelle, NICHT aus formaler Extraktion): c0×0,5 ≈ 22.981.000 EUR (Gap≈0,23 %), c0×0,7 ≈ 23.058.000 EUR
(Gap≈0,156 %) — beide als **informell** zu kennzeichnen (keine `meta.json`/`cost_breakdown.json`/`geometry.csv`
vorhanden, kein `V_TES` bekannt).

**Meldepflicht A3-M1:** Formel-vorhergesagte vs. tatsächliche TAC-Differenz (c0×1,0→1,3) weicht um 7,6 % ab, nicht
rekonziliert. Betroffen: alle vier formalen Sweep-Punkte (nur 1,0→1,3-Paar stichprobenartig geprüft, nicht alle
Paare). Fixvorschlag: `tes_sb_capex_raw`-Expression zusätzlich in `full_solution_dump.json` oder `cost_breakdown.json`
separat (nicht nur aggregiert mit HP/EK/Rohr) exportieren. Aufwand: klein (~10 Zeilen in `result_collector.py`), aber
würde eine Re-Extraktion aller betroffenen Läufe brauchen (kein Re-Solve).

### A4 — Geometrie

**A4(a) — wo wird `r_hd` gesetzt, Variable oder fest, Höhengrenze?**
Antwort: **belegt.** `configs/paper_2/storage_geometry.yaml:169,178` setzt `r_hd: 2.0` für `tes_main`/`tes_sb` — ein
FESTES Seitenverhältnis (h/d = r_hd = const.), kein Optimierungsfreiheitsgrad. Code: `calion/models/blocks/geometric_storage.py:172`
(`self.r_hd = float(r_hd)`, Konstruktorparameter). Höhengrenze: indirekt über `p_max_bar` (Druckobergrenze, siehe A4(d))
via `_h_max_from_pressure()` (Zeile 46) — keine eigenständige, direkte Höhen-Obergrenze im Code.

**A4(b) — Formeln (Mantel-/Boden-/Dachfläche, Verlust, Kosten).**
Antwort: **belegt**, Code gelesen (`geometric_storage.py:58-84`):
- Oberfläche: `A = k(AR)·V^(2/3)` mit `k(AR) = π·(AR+0,5)·(4/(π·AR))^(2/3)` (geschlossener Zylinder, Mantel+Boden+Dach
  zusammen — keine Aufteilung in Einzelflächen im Code).
- Verlust: `Q̇_loss,full [MW] = U·k(AR)·V^(2/3)·(T_TES−T_amb) / 1e6`, angewendet als KONSTANTE Rate solange der Tank
  "aktiv" ist (hängt nur von V ab, NICHT vom aktuellen Ladezustand/SoC — Zeile 507-508: `q_loss_mw = _coef *
  self.V_fixed_m3 ** (2/3)`, kein SoC-Faktor).
- Kosten: `Kosten = c0·mult·(V/v0)^b` (Zeile 377-388) — **hängt NICHT von AR/Höhe ab, nur von V.** Die Kostenkurve ist
  AR-unabhängig.

**A4(c) — Offline-Tabelle für V=30.379 m³, AR=1/2/3 (berechnet, `t_amb_c=10°C` aus `storage_geometry.yaml:55`,
`U=0,2 W/m²K`, `T_TES=T_return+ΔT_k=60+15=75°C` aus dem echten SB-S1-Lauf-Log):**

| AR | h [m] | d [m] | k(AR) | Q̇_loss,voll [MW] | Verlust/Jahr* [MWh/a] | Kosten [EUR] | Kosten [EUR/m³] |
|---|---|---|---|---|---|---|---|
| 1 | 33,82 | 33,82 | 5,536 | 0,0701 | 613,8 | 5.441.835,92 | 179,13 |
| 2 (= realer Fall) | 53,68 | 26,84 | 5,812 | 0,0736 | 644,4 | 5.441.835,92 | 179,13 |
| 3 | 70,35 | 23,45 | 6,210 | 0,0786 | 688,5 | 5.441.835,92 | 179,13 |

\* **Wichtiger Vorbehalt:** diese Spalte nimmt an, der Tank verliert das GANZE Jahr (8760h) durchgehend mit der
"Volllast"-Rate (bei `T_TES=75°C`, unabhängig vom tatsächlichen SoC — so rechnet auch das Modell selbst laut
Code, Zeile 507-508: kein SoC-Faktor). Das ist die vom Code tatsächlich verwendete Formel, ABER real ist der Tank
nicht ganzjährig auf 75°C (siehe B2 für die echte Lade-/Entladehistorie) — die Tabelle zeigt die MODELLFORMEL exakt,
keine realitätsnähere Schätzung des tatsächlich dispatchten Verlusts. AR=2 (realer Fall, `h=53,68m`) reproduziert
exakt `geometry.csv`s `h_TES_m=53,68`. **Auffällig:** 613-689 MWh/a Verlust bei `h=438 MWh` E_max bedeutet eine
rechnerische "Volllast"-Jahresverlustquote von 140-157 % der Nominalkapazität — das ist eine Eigenschaft der
Modell-ANNAHME (konstante Verlustrate unabhängig vom SoC), nicht notwendigerweise ein Fehler, aber bemerkenswert
und für die Diskussion im Paper evtl. erklärungsbedürftig. Reuter-West-Referenz (45m/43m aus dem Dokument) liegt
nahe an AR=2's 53,68m — plausible Größenordnung.

**A4(d) — `p_betr_bar=6,131` vs. `design_pressure=5,5 bar`.**
Antwort: **belegt + berechnet.** Docstring `geometric_storage.py:19`: `p_betr = p_atm + rho·g·h_TES / 1e5 ≤ p_max`
— `p_betr` ist der ABSOLUTE Betriebsdruck am Tankboden (Atmosphärendruck + hydrostatische Säule), `p_max_bar=5,5` ist
die AUSLEGUNGSOBERGRENZE (`storage_geometry.yaml:169`, Konstruktionsgrenze, nicht der tatsächliche Betriebsdruck).
Nachrechnung mit `h=53,68m`, `ρ≈960 kg/m³` (nahe 75-95°C): `p_hydrostatisch = 960·9,81·53,68/1e5 ≈ 5,057 bar` + `p_atm
1,013 bar` = **6,070 bar** — nahe am berichteten `6,131 bar` (Differenz ≈1 %, vermutlich eine leicht andere ρ-Annahme
im Code, nicht nachverfolgt). **Wichtig:** `p_betr (6,131) > p_max_bar (5,5)` — der Betriebsdruck ÜBERSTEIGT die
Auslegungsgrenze rechnerisch. Das ist kein Widerspruch, weil `p_max_bar` nur die ATMOSPHÄRISCHE Technologie-Variante
(druckentlastet am Kopf, s. `V2f`/`V2c`-Kommentare in `storage_geometry.yaml:91-151`) betrifft — die `p_betr`-Zahl in
`geometry.csv` ist vermutlich eine reine Diagnose-Kennzahl, nicht ein tatsächlich geprüftes Constraint-Limit für die
atmosphärische Technologie (**vermutet**, nicht abschließend im Code verifiziert — würde eine genauere Prüfung der
`pressure_limits_size`-Verzweigung aus V2f brauchen).

### A5 — Bilanzschluss

**A5(a) — Definition/Schwelle `closure_pass`.**
Antwort: **belegt, mit Branch-Vorbehalt (siehe Hinweis oben).** Auf `Loc_TES_Study_P2` (wo der Z4-Fix tatsächlich liegt):
`scripts/paper/extract_artefacts.py`: `closure_err_pct = abs(supply - dump - demand - losses) / demand * 100`,
`closure_pass = closure_err_pct <= 2.0` (Schwelle 2,0 %, hartcodiert). Auf `main` (wo dieser Report committet wird)
fehlt `- losses` noch — Zeile 977 dort: `closure_err_pct = abs(supply - dump - demand) / demand * 100`. `supply =
generation + net_discharge`.

**A5(b) — Re-Extraktion SB-S2/S3 mit Z4-Fix, NEUES Verzeichnis.**
Antwort: **belegt, frisch berechnet (eigene Python-Formel nach dem Z4-Fix-Prinzip angewendet, NICHT über den
Produktionscode von `main` gelaufen, da dieser den Fix noch nicht enthält — Ergebnis dennoch korrekt, da die Formel
hier direkt und nachvollziehbar implementiert wurde), NICHT in die Original-`validation.json` geschrieben** (neue
Datei: `docs/paper_2/agent_reports/reextractions/validation_SB-S2-S3_Z4fix.json`):

| Lauf | alt (H6, vor Z4-Fix) | neu (Z4-Fix, hier berechnet) |
|---|---|---|
| SB-S2-HK0 | 3,305 %, `closure_pass=false` | **0,269 %, `closure_pass=true`** |
| SB-S3-HK0 | 3,305 %, `closure_pass=false` | **0,269 %, `closure_pass=true`** |

Bestätigt: der Z4-Fix (13.10., §4cm) wurde auf diese beiden Läufe noch nicht rückwirkend angewendet (H6 war korrekt) —
mit Fix schließen beide sauber, identisch zueinander (konsistent mit A2s Befund, dass S2/S3 bit-identisch sind).

**A5(c) — MM-Residuum (1,96 %) zerlegt.**
Antwort: **teilweise belegt, teilweise offen.** `data_closure_dump_MWh = 0,0` für MM-S1-HK0 (`cost_breakdown.json`,
belegt) — dieser Term scheidet als Erklärung aus. Pumpwärme, Messfehlerstunden und Rundung wurden NICHT einzeln
quantifiziert (**offen** — würde eine stundenweise Aufschlüsselung der `Q_loss_total_MW`-Zusammensetzung brauchen,
die in Stufe 1 nicht vorlag). Verbleibende Erklärung: numerisches Rauschen zwischen der Z4-Formel (die pauschale
`Q_loss_total_MW` einrechnet) und der tatsächlichen, räumlich verteilten Verlustbilanz — **vermutet**, nicht bewiesen.

**A5(d) — MM-Netzverlust 27,5 %: Quelle, Plausibilität, Bezug zu Paper 1.**
Antwort: **berechnet + eine Korrektur zu §1.** 2.596,5 MWh / 9.433,2 MWh **Bedarf** = 27,5 % (nicht "der Erzeugung"
wie in H-Tabelle formuliert — bezogen auf `Erzeugung` [11.844,9 MWh] wären es 21,9 %; vermutlich eine
Formulierungs-Ungenauigkeit in H, keine neue Erkenntnis). Plausibilität gegen Paper 1: **offen** — kein Paper-1-Referenzwert
für Memmingen-Netzverluste in der verfügbaren Zeit nachgeschlagen; würde `docs/paper_1/` oder die dortigen
Validierungstabellen brauchen (nicht geprüft in Stufe 1 dieses Auftrags).

---

## Block B — Daten für Abschnitt 4

### B1 — Kostenzerlegung

CSV: `docs/paper_2/agent_reports/tables/B1_cost_decomposition.csv` (65 Zeilen, 5 Paare × 9 Positionen + Hilfsterme +
Total + STOPP-Quote). **Belegt**, direkt aus `real_costs_EUR`/`model_aux_terms_total_EUR` in `cost_breakdown.json`
beider Läufe je Paar berechnet (Δ = frei − PIN0, % bezogen auf PIN0-TAC wie in Spielregel 6 gefordert).

**STOPP-Regel-Check (Hilfsterm-Anteil am TOTAL-Delta):**

| Paar | Hilfsterm-Anteil am Δ | Bewertung |
|---|---|---|
| SB-S1 c0×1,0 vs PIN0 | 0,63 % | unauffällig |
| **SB-S1 c0×2,0 vs PIN0** | **18,11 %** | **nahe der 20-%-Schwelle, aber ein Denominator-Artefakt** (s.u.) |
| SB-S1 SPREIZ15 vs eigene PIN0 | 1,46 % | unauffällig |
| SB-S1 SPREIZ20 vs eigene PIN0 | 2,92 % | unauffällig |
| MM-S1 vs PIN0 | 11,87 % | erhöht, aber MM-Δ ist ohnehin klein (Rauschband) |

**Einordnung c0×2,0 (berechnet):** das TOTAL-Delta selbst ist winzig (−1.633,44 EUR/a — konsistent mit dem bereits
bekannten Fast-Null-Punktwert an diesem Sweep-Punkt). Der Hilfsterm-Delta ist nur −295,84 EUR (`Dump_cost_EUR`,
einziger Posten mit |Δ|>1 EUR) — 18,11 % eines SEHR kleinen Nenners, kein großer absoluter Hilfsterm-Beitrag. **Kein
STOPP gemäß Geist der Regel** (die soll große, das Ergebnis verzerrende Hilfsterme fangen, nicht Prozentrauschen bei
einem Delta nahe Null), aber formal nahe der Schwelle — der Auftraggeber sollte das selbst bewerten, daher hier
explizit gemeldet statt stillschweigend übergangen.

### B2 — Speicherbetrieb SB-S1 (c0×1,0)

**Belegt/berechnet, direkt aus `dispatch_hourly.csv` (echte Stundenwerte):**
- **Vollzyklen/a:** 30.635,9 MWh Entladung / 438 MWh E_max = **69,95 Vollzyklen/a**. Ladung 32.556,7 MWh/a
  (Verlustdifferenz 1.920,8 MWh/a ≈ Standing-Loss + Wirkungsgradverluste, konsistent mit dem bereits dokumentierten
  `net_storage_MWh=-1.920,8`, Z4-Validierung).
- **Leistungsgrenze (109,5 MW):** 125 Stunden/a am Lade-Limit, **0 Stunden** am Entlade-Limit — die Ladeseite ist
  häufiger bindend als die Entladeseite.
- **Monatsprofil (Laden/Entladen/mittlerer SoC):** stark saisonal, Schwerpunkt Januar-März und Oktober (März allein
  9.445/9.017 MWh), nahezu inaktiv Juni-August (44,7-506,4 MWh) — deutet auf heizperiodengetriebenen, nicht
  gleichmäßig übers Jahr verteilten Betrieb hin.
- **Welche Bestandsanlage läuft weniger (PIN0 vs. S1, Jahressummen):**

| Erzeuger | PIN0 [MWh/a] | S1 [MWh/a] | Δ [MWh/a] |
|---|---|---|---|
| Gaskessel | 59.245,8 | 45.299,1 | **−13.946,6** (größter Rückgang) |
| KWK (HKW) | 164.219,0 | 168.888,3 | +4.669,2 |
| Biomasse | 432.181,5 | 435.897,1 | +3.715,6 |
| WP (HP) | 0,0 | 8.639,4 | +8.639,4 (neu, war in PIN0 =0) |
| EK | 5.309,2 | 3.902,5 | −1.406,7 |

**Mechanismus (berechnet/vermutet):** der größte Einzeleffekt ist eine Verdrängung des Gaskessels (−13,9 GWh/a) zugunsten
von KWK/Biomasse/WP. Da S1 sowohl TES ALS AUCH WP/EK gleichzeitig frei investierbar sind, ist aus dieser Paar-Differenz
allein **nicht trennbar**, wie viel davon auf den Speicher selbst vs. die WP zurückgeht — siehe B3. Das Monatsprofil
(Lastspitzen-Saisonalität, nicht gleichmäßige Arbitrage) spricht eher für **Mindestlast-/KWK-Fahrweise-Pufferung**
als für reine Day-Ahead-Preisarbitrage als Haupttreiber — konsistent mit dem Preisspreizungs-Befund (§4co, nur auf
`Loc_TES_Study_P2`: Wert verdreifacht sich bei mehr Volatilität), was beide Mechanismen (Mindestlast-Glättung UND
Preisarbitrage) gleichzeitig plausibel macht, ohne dass diese Daten sie sauber trennen. **Offen:** SPREIZ20-Speicherbetrieb
(vom Auftrag mitgefordert) aus Zeitgründen nicht mehr im Detail durchgerechnet — nur die Kostenzerlegung liegt vor (B1).
Die Entlademaske (2.025 gesperrte Stunden, `discharge_mask_hours_blocked` in `scenario_meta.json`) wurde nicht
gesondert gegen die Dispatch-Daten geprüft (**offen**).

### B3 — TES vs. WP/EK

**Belegt**, HP/EK-Spitzendispatch (Proxy für gebaute Leistung, aus `dispatch_hourly.csv`-Spaltenmaxima) je Lauf:

| Lauf | HP-Peak [MW] | EK-Peak [MW] |
|---|---|---|
| SB-PIN0 | 0,0 | 9,9 (Bestand-P2H, nicht investiert) |
| SB-S1 (c0×1,0) | 2,51 | 9,9 |
| SB-S2 | 2,14 | 9,9 |
| SB-S1 c0×2,0 | 2,35 | 9,9 |
| MM-PIN0 | 0,0 | 0,0 |
| MM-S1 | 0,0 | 0,10 |

EK bleibt bei SB konstant 9,9 MW über ALLE Läufe (auch PIN0!) — das ist das **Bestand-`p2h_existing`** (9,9 MW,
laut Topologie-Kommentar in `Stadtbach_topo.yaml:29`), NICHT investierte Kapazität; `ek_sb`s eigene Investition
bleibt in allen geprüften Läufen bei 0. HP-Größe variiert nur wenig (2,1-2,5 MW) über S0/S1/S2/c0×2,0 — **relativ
unempfindlich gegenüber TES-Größe/-Standort.**

**Trennbarkeit (vermutet, aus obiger Beobachtung):** da die HP-Größe über sehr unterschiedliche TES-Konfigurationen
kaum variiert, ist eine GROBE Trennung plausibel (TES-Wert ≈ Gesamtwert minus ein relativ stabiler HP-Beitrag), aber
NICHT sauber aus den vorhandenen Läufen isolierbar, da PIN0 BEIDE (HP und TES) gleichzeitig auf 0 setzt.

**Bereits vorhandene Szenarien für eine saubere Trennung (belegt, Konfiguration geprüft):**
- `SB-TESONLY-HK0` (`configs/paper_2/scenarios.yaml:911-922`) existiert bereits fertig konfiguriert: TES frei an
  j_hkw, HP/EK auf 0 fixiert. Alter Lauf nur unter Vor-V1-V8-Code (`output/paper2_runs_v3b/` hat nur MM-Variante,
  keine SB-Variante gefunden) — **kein aktueller V1-V8-Lauf vorhanden.**
- Ein symmetrisches "HP/EK-ONLY" (TES fest auf 0, HP/EK frei) existiert nicht unter eigenem Namen, ließe sich aber
  trivial aus `SB-S0-HK0` (TES via `tes_off_sb`-Anker aus, HP/EK frei) ableiten — dafür ebenfalls kein frischer
  V1-V8-Lauf gefunden.

**Aufwandsschätzung (vermutet, basierend auf den bereits gelaufenen Z3-PIN0-Zeiten von 580-2.246s bzw. dem
Standardprotokoll):** je ein SB-Lauf (TimeLimit 28.800s/8h Matched-Effort-Standard, Warmstart aus `SB-S1-HK0` oder
`SB-S0-HK0-PIN0`) für TESONLY und HP/EK-ONLY — realistisch 2 Läufe à bis zu 8h, da PIN0-ähnlich kleine Investitionsfreiheit
oft deutlich schneller konvergiert (Z3-PIN0-Läufe brauchten nur 580-2.246s) — **grobe Schätzung 1-4h Gesamtrechenzeit
für beide zusammen**, kein neuer Code nötig.

### B4 — Heizkurve

**Belegt.** Scenario-IDs mit `HK1`/`HK2` existieren durchgängig in `scenarios.yaml` (z. B. `SB-S1-HK1`, `SB-S1-HK2`,
`MM-S1-HK1`, `MM-S1-HK2`). **Kein `output/v7_final/`-Verzeichnis für irgendeine `HK1`/`HK2`-Variante gefunden** (nur
`HK0` ist unter dem aktuellen V1-V8-Stand gelaufen) — die "Heizkurve ≤0,1%"-Aussage (referenziert als §4ao, 02.10.)
stützt sich demnach auf einen **älteren Lauf-Stand**, nicht auf V1-V8. **Offen:** exakte Quelle/Konfiguration von §4ao
wurde in der verfügbaren Zeit nicht nachgeschlagen (Datei `MODEL_AND_DOE_CONTROL.md` ist sehr lang; §4ao liegt vor
dem in diesem Auftrag relevanten Abschnittsbereich §4ck ff. und wurde nicht erneut gelesen). Aufwandsschätzung für
einen HK-Vergleich unter V7: **vermutet**, analog zu B3 — ein Lauf je HK-Stufe (HK1/HK2) für SB-S1 und MM-S1, je bis
zu 8h/4h Matched-Effort, d. h. ca. 4 weitere Läufe, 16-24h Gesamtrechenzeit grob geschätzt.

### B5 — Konvergenz- und Provenienztabelle

CSV: `docs/paper_2/agent_reports/tables/B5_convergence_provenance.csv` (31 Zeilen: 29 Läufe mit Export + 2
Lücken-Zeilen für c0×0,5/×0,7). Spalten: scenario_id, network, PIN0-Rolle, UB (`obj_eur`), LB (**berechnet**
`UB·(1−gap)`), Gap%, Status, Solve-Zeit, n_vars/n_constraints, tatsächliche Solver-Parameter (aus dem Gurobi-Log
geparst, `scripts/paper_2/verify_solver_params.py`), Warmstartquelle, Git-Commit, Config-Hash, Export-Verzeichnis.

**Wichtiger Methodik-Fund beim Bau dieser Tabelle (eigene Meldepflicht, nicht Teil der ursprünglichen H-Liste):**
`gurobi_SB-S1-HK0.log`, `gurobi_SB-S2-HK0.log`, `gurobi_SB-S3-HK0.log`, `gurobi_MM-S0-HK0-PIN0.log`,
`gurobi_MM-S1-HK0.log` sind **kumulative** Logs — dieselbe Datei wird seit Juni 2026 über JEDEN historischen Lauf
dieser `scenario_id` hinweg immer wieder AN den gleichen Pfad angehängt (`output/logs/gurobi_<scenario_id>.log`,
kein Job-isolierter Pfad). `verify_solver_params.parse_actual_params()` nimmt das LETZTE Vorkommen jedes Parameters
**über die GESAMTE Datei** — bei einer kumulativen Datei kann das aus einem älteren, nicht mehr relevanten Lauf-Block
stammen, nicht aus dem aktuellen. Erste (fehlerhafte) Version dieser Spalte zeigte z. B. `Threads=2.0` für
SB-S1-HK0 — nach Korrektur (nur den letzten `Gurobi ... logging started`-Block extrahiert) verschwindet dieser Wert
(kein explizites `Threads` im relevanten Block, Default/Auto). **Korrigierte Werte in der CSV**, aber dies ist ein
allgemeines Risiko für JEDE künftige Log-Analyse dieser fünf Dateien.

**Meldepflicht B5-M1:** `verify_solver_params.py` sollte eine Blockgrenzen-Option (z. B. "nur ab Zeile X" oder "nur
letzter Block") bekommen, sonst liefert es auf kumulativen Logs potenziell falsche Werte. Betrifft jede Nutzung
dieses Tools auf den 5 genannten Scenario-IDs. Aufwand: klein (~10 Zeilen).

**Lücken (aus B5 direkt ablesbar, hier zusammengefasst):** Git-Commit ist für KEINEN Lauf gespeichert (weder in
`meta.json` noch `run_export.json`) — durchgehend "offen". c0×0,5/×0,7 haben keine UB/LB/Gap-Spalten (kein Export).

### B6 — Tankanbindung und Kandidatenknoten

**Belegt (teilweise).** `cap_power_MW` wird NICHT im gelesenen Code-Ausschnitt als reine `E/4h`-Regel gefunden —
für SB-S1 ist `cap_power_MW=109,5` bei `E_TES_max_MWh=438,0`: 438/109,5 = 4,0 h, konsistent mit einer E/4h-Heuristik,
aber die exakte Codezeile, die dieses Verhältnis FESTLEGT, wurde in der verfügbaren Zeit nicht lokalisiert (**offen**).
Begrenzung der Anbindung: siehe A2(c) — die einzige Rohrleitung (Durchmesser) limitiert die physikalisch mögliche
Leistung, kein separates "Anbindungskosten"-Element im Kostenmodell gefunden (**vermutet**, nicht abschließend
durchsucht). Vollständige Kandidatenknotenliste (alle möglichen `tes_node`-Werte je Netz) wurde NICHT systematisch
aus dem Code extrahiert (**offen** — würde eine Suche nach allen `tes_node:`-Werten in `scenarios.yaml` plus Abgleich
mit der Netzwerktopologie brauchen, aus Zeitgründen nicht mehr geleistet).

---

## Block C — Machbarkeit (nur Schätzung, keine Läufe)

### C1 — Siting-Enumeration (Study C)

**Vermutet (Schätzung, wie gefordert, kein Lauf).** SB hat laut Topologie-Config 33 Knoten, davon ein Teil reine
Durchgangs-/Verbraucherknoten ohne Erzeugungs-/Anbindungsrelevanz. Realistisch als TES-Kandidaten kommen nur Knoten
mit ausreichender Rohranbindung infrage (vgl. A2(c): j_man scheidet strukturell für einen S1-großen Tank fast aus) —
grobe Schätzung **5-10 sinnvolle Kandidatenknoten**, nicht alle 33. Ein fixierter Tank (438 MWh, Dispatch-MILP, kein
Investitions-Freiheitsgrad mehr für TES selbst) sollte deutlich schneller konvergieren als die vollen Investitions-MILPs
(Analogie: PIN0-Läufe mit 580-2.246s ggü. 8h für volle Investitionsfreiheit) — **Schätzung 0,5-2h je Knoten** mit
Warmstart aus S1. Bei 5-10 Knoten: **grob 3-20h Gesamtrechenzeit**, gut parallelisierbar (wie die Z3-Batches in dieser
Session gezeigt haben). Dominanz per Konstruktion über Sprosse 0 (`build=0`) ist bereits als Konzept etabliert (jeder
Kandidat kann mindestens `build=0` erreichen, vgl. PIN0 als Referenz) — **ja, plausibel nutzbar**, nicht neu zu beweisen.

Für MM: bekannt (vermutet aus H-Tabelle übernommen, nicht neu verifiziert), dass ein Forced-Build bei 23,9 MWh
infeasible ist (Regret-Lauf, AA1) — ein SEHR kleiner fixer Tank (deutlich unter 23,9 MWh) wäre ein vorsichtigerer
erster Test, bevor eine volle Enumeration versucht wird. Gleiche Grobschätzung (Knotenzahl × 0,5-2h) gilt strukturell,
MM hat ein kleineres Netz → vermutlich am unteren Ende der Spanne.

### C2 — Nachlauf-Vorschläge mit Aufwand

| # | Zweck | Läufe | Warmstart | Zeit (geschätzt) | Erwarteter Gewinn |
|---|---|---|---|---|---|
| (i) | SB-S2/S3 mit S1-Lösung neu starten (statt altem S0-Wert) — prüft die A2-Stuck-Warmstart-Hypothese | 2 (SB) | `output/v7_final/SB-S1-HK0` | je bis 8h (Matched-Effort-Standard) | klärt, ob S2/S3s "kein Speicher"-Befund robust ist oder nur Warmstart-Artefakt |
| (ii) | SB-MONTHLY frei neu, nach A1-Klärung | 0 nötig | — | — | **A1 zeigt: Intervall bereits gültig, kein Neulauf nötig** |
| (iii) | c0×0,5/×0,7 sichern/fertigstellen | 2 (SB) | `output/v7_final/SB-S1-HK0` | je bis 8h, mit `NodefileStart` (nur auf `Loc_TES_Study_P2` verfügbar) | schließt die Lücke in der c0-Sweep-Tabelle (B5) |
| (iv) | c0×1,3-2,0 mit TES-Größe als freie Variable OHNE Warmstart-Bindung | 2-4 (SB) | KEIN Warmstart (bewusst, um A2/AA3-Stuck-Problem zu umgehen) | je bis 48h (High-Stakes-Protokoll wie AA3) | löst den in §4cn benannten Vorbehalt (×1,3/×1,5 vermutlich stuck) — direkt relevant für die Eintrittsschwellen-Aussage im realen Kostenband |
| (v) | MM-Regret-Infeasibilität, IIS-Workaround | 0 (Diagnose, kein neuer Solve) | — | — | LP schreiben + direkt mit `gurobipy.read()` laden (umgeht den kaputten Pyomo-`_solver_model`-Zugriff) — **vermutet funktionsfähig, nicht getestet** |

---

## Block D — Dokumentation

### D1

Siehe `docs/paper_2/agent_reports/DRAFT_4ck_ff.md` — **bereits vollständig vorhanden** (extrahiert aus dem
`Loc_TES_Study_P2`-Branch, wo diese Abschnitte während der referenzierten Arbeitssession laufend geschrieben wurden,
siehe Branch-Hinweis oben). Nicht neu verfasst, nicht in das Hauptdokument eingefügt.

---

## Meldepflichten (Zusammenfassung)

| Fund | Betroffene Läufe | Fixvorschlag | Aufwand |
|---|---|---|---|
| A1-M1: `peak_import_MW` unter Monatsmodus unzuverlässig (meist `1,0`) | alle 4 geprüften Monats-Läufe außer SB-frei | `max(P_buy_peak_month)` statt `P_buy_peak` lesen | klein (~15 Zeilen) |
| A2-M1: SB-S2/S3 "kein Speicher" hat dieselbe Stuck-Warmstart-Einschränkung wie AA3 ×1,3/×1,5 | SB-S2-HK0, SB-S3-HK0 | Re-Solve mit S1-Warmstart statt altem S0-Wert | siehe C2(i) |
| A3-M1: Formel-vs-TAC-Delta weicht 7,6 % ab, nicht rekonziliert | mind. c0×1,0→1,3-Paar | `tes_sb_capex_raw` separat exportieren | klein, + Re-Extraktion |
| B5-M1: `verify_solver_params.py` liest über kumulative Logs falsche (zu alte) Parameterwerte | SB-S1/S2/S3-HK0, MM-S0/S1-HK0-Logs | Blockgrenzen-Option ergänzen | klein (~10 Zeilen) |
| **Branch-Divergenz:** Z4-Fix, Preisspreizung, 12 Szenarien, §4ck-§4cp existieren nur auf `Loc_TES_Study_P2`, nicht auf `main` | betrifft jede künftige Arbeit auf `main`, die sich auf diese Ergebnisse verlässt | Branch nach `main` mergen (Entscheidung beim Auftraggeber) | — |

**STOPP — Stufe 1 abgeschlossen. Warte auf Freigabe für Stufe 2 (Läufe, Fixes).**
