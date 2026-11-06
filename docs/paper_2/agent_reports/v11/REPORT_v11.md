# REPORT v11 — Diagnose v10 + Wechsel auf Festauslegungs-Enumeration

Antwort auf `docs/paper_2/agent_prompts/v11_Diagnose.md`, bezogen auf `docs/paper_2/agent_reports/v10/REPORT_v10.md`
(p2_v9_consolidation@e2ea894). Teil A ist eine reine Lese-/Rechenauswertung der vorhandenen v10-Lösungsdumps
(`output/v9/`, `output/v10/` nach der B2-Migration unten), **kein neuer Solve**. Teil C (Festauslegungs-Laufzeittest)
ist in diesem Auftrag mit keinem Punkt `[x]` markiert und wurde zusätzlich vom Nutzer explizit zurückgestellt
("noch keine neuen Runs starten ... der Server ist sehr ausgelastet") — entsprechend **nicht ausgeführt**, nur
geplant/vorbereitet, siehe Abschnitt C unten.

---

## Widersprüche (vorab)

**W1 — Der zentrale Befund dieses Reports: `HKW_TO_MAN_Q_consumer` ist NICHT das, was REPORT_v10 daraus gelesen hat.**
v10 hat `HKW_TO_MAN_Q_consumer` als "WP-Einspeisung via hkw_to_man" interpretiert und daraus "0 Stunden Rückfluss"
geschlossen. Das ist falsch — siehe A1. Die Leitung ist bidirektional; die tatsächliche Flussrichtung steht im
Vorzeichen von `HKW_TO_MAN_m_dot` (bzw. `flow_dir`), nicht in `Q_consumer` (das bleibt in diesem Lauf durchgehend
positiv, unabhängig von der Flussrichtung). Das korrigiert gleichzeitig den in diesem Auftrag aufgeworfenen Widerspruch
"WP liefert 48.886 MWh/a, MAN braucht nur ~17.7 MWh/a" — dieser Widerspruch löst sich auf, weil `Q_consumer`
NICHT die tatsächliche WP-Wärme ist (die ist `hp_sb_Q` = 47.291,6 MWh/a in C1), sondern eine zweite, davon
unabhängige Größe, die am Knoten j_man fälschlich noch einmal als Zufluss gezählt wird (Doppelzählung, siehe A1).

**W2 — Die STOPP-Regel trifft auch C2−PIN0, nicht nur C1−PIN0.** Der Auftrag listet nur C1−PIN0 (≈29%) als
Regelverstoß. Dieselbe Rechnung für C2−PIN0 ergibt **36,05%** (noch deutlicher über der 20%-Schwelle). Nur
C2−C1 bleibt mit 19,71% knapp UNTER der Schwelle — aber da beide Einzelvergleiche gegen PIN0 bereits ungültig
sind (derselbe j_man-Bug), ist auch C2−C1 nur mit Vorsicht zu lesen (siehe A2).

**W3 — v10-M2s eigene Ursachenvermutung (power-CAPEX fehlt in der Kostenzerlegung) wird durch Code-Prüfung NICHT
bestätigt.** Siehe A4: der Code-Pfad ist korrekt verdrahtet, der power-CAPEX-Term fehlt nicht. Die zahlenmäßige
Nähe (76,6 k€ geschätzt vs. 82.204 € Residuum) ist wahrscheinlich Zufall. Ursache bleibt offen.

**W4 — Die Doku-Kopfzeile in `Stadtbach_topo.yaml` widerspricht der tatsächlichen Knoten-Verdrahtung.** Zeile 36:
"hp_sb: HP at j_hkw" vs. Zeile 649-650: "Physical WRG source is at j_man; the HP is co-located at the production
hub [j_hkw] as a modeling simplification". Tatsächlich zeigt die direkte Prüfung der Bilanzgleichung (A1), dass
`hp_sb_Q` in C1/C2 unzweifelhaft in j_mans eigene Knotenbilanz eingeht (nicht in j_hkws) — die scenario-level
`hp_node`-Überschreibung (v9/E5) verlegt die WP tatsächlich nach j_man, der Kommentar ist veraltet. Keine
Auswirkung auf die hier berichteten Zahlen, aber ein Doku-Fix wäre angebracht (nicht Teil dieses Auftrags).

## Meldepflichten

**v11-M1 (NEU, zentral) — j_man-Knotenbilanz zählt bidirektionale Pipe-Wärme bei Rückfluss doppelt.**
Für eine "secondary mixed"-Knotenbilanz (hier: j_man) verwendet `constraint_builder.py` (Zeilen 613-669)
`{PIPE}_Q_consumer` ungeprüft als **positiven** Zufluss-Term, unabhängig von der tatsächlichen Flussrichtung.
Für die PRIMARY-PRODUCER-Bilanz (j_hkw) gibt es dagegen einen expliziten vorzeichenrichtigen Pfad
(`_bidi_signed_q_terms`, Zeilen 396-451: "positive = j_hkw sends forward; negative = receives backward"). Dieser
vorzeichenrichtige Pfad existiert für SECONDARY-mixed-Knoten mit bidirektionaler Zuleitung **nicht** — ein
Lückenfall, der vor v9/E5 (WP-Standort an j_man, erste bidirektionale Leitung an einem Nicht-Primärerzeuger-Knoten)
nie auftrat. Folge: in 4.900/8.760 h (C1, 55,9%) bzw. 4.779/8.760 h (C2, 54,6%) läuft `HKW_TO_MAN_m_dot` negativ
(Wasser fließt tatsächlich von j_man zurück nach j_hkw), aber `Q_consumer` bleibt in diesem Lauf trotzdem positiv
(≈ hp_sb_Q) und wird in j_mans Bilanz ALS ZUFLUSS addiert — zusätzlich zu `hp_sb_Q`, das ohnehin schon als
lokale Erzeugung in derselben Bilanz steht. Das Modell bekommt dadurch pro Stunde bis zu ~2× die reale WP-Wärme
auf der Angebotsseite von j_man und muss den Überschuss über `Q_dump_j_man` entsorgen. Direkt verifiziert:
`hp_sb_Q[t] + Q_consumer[t] == demand[t] + Q_dump_j_man[t]` gilt exakt (Residuum < 1e-6 MWh) für alle 8.760 h in
C1 UND C2 — das ist die Bilanzgleichung, die tatsächlich gelöst wird, und sie erklärt den gesamten Dump-Anstieg
(PIN0: 0 MWh an j_man, da dort kein lokaler Erzeuger hängt; C1: 78.397,8 MWh; C2: 85.858,0 MWh). Das ist ein
reiner Buchhaltungsfehler im Vorzeichen, kein physikalisches Ergebnis — **C1 und C2 sind damit beide nicht
belastbar**, bis diese Lücke geschlossen ist (Code-Fix: entweder denselben `_bidi_signed_q_terms`-Mechanismus
auch für secondary-mixed-Knoten mit bidirektionaler Zuleitung anwenden, oder `Q_pipe_in` für diesen Fall explizit
vorzeichenrichtig aus `m_dot`/`flow_dir` neu aufbauen statt `Q_consumer` zu verwenden). Dieser Fix ist NICHT
Teil dieses Auftrags (kein B-Punkt deckt ihn ab) — er ist der wichtigste Kandidat für den nächsten Auftrag,
wichtiger als B1/B3.

**v11-M2 (NEU) — Demand_charge_cost_EUR ≈ 2× der aus `P_buy_peak` berechenbare Wert, für REF UND S1 gleich.**
Siehe A5: aus `P_buy[t]` (Netzbezug) berechnet sich (egal ob Jahres- oder Monatsspitzen-Abrechnung, der Peak
tritt in C2 in allen 12 Monaten gleich auf) ein Leistungsentgelt von 20.920,19 € (REF) bzw. 188.304,59 € (S1).
Die tatsächlich berichteten `Demand_charge_cost_EUR` sind 41.840 € bzw. 376.609 € — in beiden Fällen **exakt**
das Doppelte (41.840/20.920,19 = 1,99999; 376.609/188.304,59 = 1,99999). Das ist kein Zufall, sondern ein
strukturelles Merkmal (evtl. zwei Demand-Charge-"Zonen" auf demselben physischen Netzanschluss, siehe
`zone_demand_charge_values`-Mechanismus in `result_collector.py` Zeilen 806-821) — Ursache hier nicht abschließend
isoliert (würde Live-Modell-Zugriff bzw. einen Debug-Instrumentierungs-Rerun erfordern, außerhalb des
"nur Lesen/Rechnen"-Rahmens dieses Auftrags). Empfehlung für einen Folgeauftrag: prüfen, ob `zone_demand_charge_values`
für Stadtbach zwei Zonen mit identischem Netzanschluss/identischem Peak enthält.

**v11-M3 (Fortführung v10-M1, ERLEDIGT durch B2 unten) — Ergebnisarchiv-Kollisionsschutz.** Siehe Teil B.

**v10-M2 (fortgeführt, weiterhin OFFEN) — Objective_residual_EUR (82.204 € in C2).** Siehe A4: die im Auftrag
vorgeschlagene Ursache (power-CAPEX fehlt) ist durch Code-Prüfung NICHT bestätigt. Ursache bleibt offen,
B1 (Kostenzeile ergänzen) bleibt entsprechend korrekt unmarkiert/nicht umgesetzt.

---

## A1 — Wärmebilanz j_man (C1, C2)

**Methode:** direkte Variablenauswertung aus `full_solution_dump.json` (Pyomo-Lösungswerte) für beide Läufe,
stündlich, plus `unified_timeseries.csv` für `j_man_Q_demand`. Kein neuer Lauf.

**Die 48.886 MWh (C1) sind NICHT WP-Wärme.** Zwei getrennte Größen:
- `hp_sb_Q` (reale WP-Wärmeleistung, Summe der Kanäle `hp_sb_Q_def` 42.349,9 MWh + `hp_sb_Q_wrg` 4.941,7 MWh):
  **47.291,6 MWh/a** (C1), **51.009,3 MWh/a** (C2). Max 11,90 MW (C1) / 13,79 MW (C2) — passt zur gebauten
  WP-Kapazität.
- `HKW_TO_MAN_Q_consumer` (Pipe-Variable, s.u.): **48.886,2 MWh/a** (C1), **52.628,8 MWh/a** (C2). Max 11,91 MW /
  13,79 MW — fast identisch zu `hp_sb_Q`, aber eine ANDERE Variable mit eigener Formel.

**Flussrichtung (`HKW_TO_MAN_m_dot`, Vorzeichen: positiv = j_hkw→j_man, negativ = j_man→j_hkw per
`constraint_builder.py` Zeile 438):** C1: 4.900/8.760 h (55,9%) negativ (Rückfluss), 3.659 h positiv, 201 h ≈0.
C2: 4.779/8.760 h (54,6%) negativ. `flow_dir`-Binärvariable stimmt mit `sign(m_dot)` in 8.706/8.760 h überein
(54 Abweichungen, numerisches Rauschen an der Nulllinie, irrelevant).

**Die Bilanzgleichung, die tatsächlich gelöst wird (verifiziert, Residuum < 1e-6 MWh über alle 8.760 h, beide
Läufe):**

```
hp_sb_Q[t] + HKW_TO_MAN_Q_consumer[t] == j_man_Q_demand[t] + Q_dump_j_man[t]
```

Stichprobe C1, Stunde 0 (m_dot = −56,0 kg/s, also Rückfluss): hp_sb_Q=11,897 MW, Q_consumer=11,908 MW,
demand=9,71 MW → dump = 11,897+11,908−9,71 = **14,094 MW** ✓ (exakt der berichtete Wert). **`Q_consumer` bleibt
in dieser Stunde positiv, obwohl der Massenstrom negativ ist** — d.h. `Q_consumer` ist in der aktuellen
Modellformulierung für diese bidirektionale Leitung keine vorzeichenrichtige "Netto-Zufluss"-Größe, sondern wird
unabhängig von der Flussrichtung mit ungefähr demselben Betrag wie `hp_sb_Q` berechnet (die Leitung transportiert
in Rückfluss-Stunden im Modell weiterhin "Wärme Richtung j_man", obwohl physikalisch das Wasser in die andere
Richtung fließt). Das ist der Doppelzählungs-Mechanismus aus v11-M1.

**Schließt die Bilanz WP + Zufluss = MAN + Dump + Verluste?** Ja, exakt — aber "Zufluss" ist hier KEIN echter,
vorzeichenrichtiger Netto-Pipe-Zufluss, sondern die oben beschriebene fehlerhafte `Q_consumer`-Größe. Die Bilanz
"schließt" nur deshalb, weil `Q_dump_j_man` als Freiheitsgrad den künstlichen Überschuss auffängt.

**Korrektur gegenüber REPORT_v10:** Die dortige Aussage "WP-Einspeisung via hkw_to_man: ... 0 Stunden Rückfluss"
beruhte auf `Q_consumer`, das per Konstruktion in diesem Lauf nie negativ wird — das ist aber NICHT dasselbe wie
"die Leitung fließt nie rückwärts" (sie tut es in >54% der Stunden). Die Aussage ist hiermit korrigiert: die
Leitung läuft mehrheitlich in Rückwärtsrichtung (j_man→j_hkw); was tatsächlich als "WP-Wärme" zu zählen ist, ist
`hp_sb_Q`, nicht die Pipe-Variable.

## A2 — Dump nach Knoten und Ursache (PIN0, C1, C2)

**Dump-Preis:** `dump_cost_eur_per_mwh_th` ≈ 5,00 €/MWh (verifiziert: 395.192,88 €/79.038,58 MWh = 5,0003 €/MWh
für C1; 430.337,20 €/86.067,44 MWh = 5,0001 €/MWh für C2 — konsistent).

| Knoten | PIN0 [MWh/a] | C1 [MWh/a] | C2 [MWh/a] |
|---|---|---|---|
| j_man | 0 | **78.397,76** | **85.858,04** |
| j_bmhkw | 217,13 | 214,89 | 60,43 |
| j_gtost | 203,41 | 207,94 | 144,60 |
| j_hkw | 111,39 | 111,39 | 0 |
| j_pss | 4,07 | 5,61 | 3,49 |
| j_psw | 1,79 | 100,99 | 0 |
| **Summe** | **537,81** | **79.038,58** | **86.067,44** |

j_man dominiert mit >99% des gesamten Dumps in C1/C2. Die übrigen Knoten (bmhkw, gtost, hkw, pss, psw) sind
klein und ändern sich zwischen PIN0/C1/C2 nur geringfügig — plausibel normale Rundungs-/Mindestlast-Dumps
(z. B. Biomasse-KWK unterhalb Mindestlast kurzzeitig), nicht Gegenstand dieses Befunds. **Erzeuger in den
j_man-Dump-Stunden:** ausschließlich `hp_sb` (der einzige lokale Erzeuger an j_man) — der Dump IST der
rechnerische Überschuss aus v11-M1, kein eigenständiges physikalisches Phänomen (kein Notkühler, keine
Abwärme-Rückkühlung — beide wären plausible reale Mechanismen, aber die Zahlen hier sind ein Modellartefakt,
nicht aus echten Netzdaten ableitbar). **Ist ein Dump an j_man im realen Netz vorhanden?** Nicht bekannt/nicht
Gegenstand der Validierungsdaten (außerhalb des Scopes einer reinen Modell-Diagnose); angesichts v11-M1 ist die
Frage ohnehin erst nach dem Code-Fix sinnvoll neu zu stellen.

**STOPP-Regel je Vergleich (Δ Dump_cost / Δ Objektiv, Schwelle 20%):**

| Vergleich | Δ Objektiv [€] | Δ Dump_cost [€] | Anteil |
|---|---|---|---|
| C1 − PIN0 | −1.364.695,61 | +392.503,85 | **28,76%** → STOPP |
| C2 − PIN0 | −1.186.373,41 | +427.648,18 | **36,05%** → STOPP |
| C2 − C1 | +178.322,20 | +35.144,32 | 19,71% → knapp unter Schwelle |

Beide Einzelvergleiche gegen PIN0 verletzen die eigene Regel (W2). C2−C1 liegt knapp darunter, ist aber durch
v11-M1 ebenfalls kontaminiert (beide Seiten tragen den gleichen Fehlermechanismus, in unterschiedlicher Stärke).
**Fazit: keiner der drei v10-Vergleiche ist derzeit belastbar.**

## A3 — Strom der Wärmepumpe

**Keine elektrische Leistungsvariable für `hp_sb` im Lösungsdump** (nur `hp_sb_Q`, `hp_sb_Q_def`, `hp_sb_Q_wrg` —
thermisch; anders als `ek_sb`, das `EK_SB_Pel` explizit führt, siehe A5). Elektrische Arbeit lässt sich daher nur
über das COP-Modell schätzen, nicht exakt aus dem Dump auslesen:
- Default-Kanal (`hp_sb_Q_def`, cop_fallback=3,0 laut Config): 42.349,9 MWh_th / 3,0 ≈ **14.116,6 MWh_el**
  (Schätzung, konstanter Fallback-COP).
- WRG-Kanal (`hp_sb_Q_wrg`, Lorenz-COP aus `WRG_1_Celsius`, eta=0,75, FQ=0,10, Sink 99/60°C): typischerweise
  höherer COP (4-6) als der 3,0-Fallback, aber nicht exakt aus den vorhandenen Exportdaten rekonstruierbar ohne
  die Lorenz-Formel live nachzurechnen (außerhalb des Scopes dieser reinen Dateiauswertung). Grobe Bandbreite:
  **800-1.250 MWh_el** für 4.941,7 MWh_th bei COP 4-6.
- **Gesamtschätzung C1: ≈ 15.000-15.400 MWh_el/a** (Bandbreite, nicht exakt).

**Warum bleibt `Grid_energy_cost_EUR` praktisch unverändert (+425,7 € in C1)?** `electricity_purchase_MW`
(Netzbezug) summiert sich nur auf **682,95 MWh/a** in C1 — winzig gegenüber der ≈15.000 MWh_el WP-Last. Der
Strom der WP kommt damit ganz überwiegend NICHT aus Netzbezug, sondern aus **reduziertem KWK-Eigenverbrauch**
(weniger Verkauf ans Netz): `Grid_sell_revenue_EUR` verbessert sich (wird weniger negativ) um +2.350.761,7 €
(C1 vs. PIN0) bzw. der entsprechende Vergleich für C2 — die WP "bezahlt" sich elektrisch über entgangenen
KWK-Stromverkauf, nicht über Netzbezug. Das erklärt die beobachtete Unveränderlichkeit von `Grid_energy_cost_EUR`
vollständig und schlüssig.

**WRG1Q_MW-Quellenbegrenzung (max. 11,73 MW):** `hp_sb_Q_wrg` erreicht im gesamten Jahr max. **11,056 MW**,
durchgehend unterhalb der genannten 11,73-MW-Grenze — konsistent mit Einhaltung der Quellenbegrenzung. Eine
vollständige stundenweise Prüfung gegen die zeitvariable `WRG1Q_MW`-Spalte selbst (statt gegen deren Jahresmaximum)
wurde in dieser Lese-Auswertung NICHT durchgeführt (Datei nicht in der verfügbaren Zeit lokalisiert) — die
beobachtete Konsistenz ist ein starkes, aber kein vollständig formales Indiz. Ein "Default-Kanal ohne
Quellbegrenzung" existiert: `hp_sb_Q_def` ist nicht an `WRG1Q_MW` gekoppelt (separate Variable, trägt den
cop_fallback=3,0) — das ist laut Scenario-Design so vorgesehen (Default-COP-Kanal für Lastanteile oberhalb der
WRG-Kapazität).

## A4 — v10-M2-Hypothesenprüfung (Residuum 82.204 €)

**Code-Pfad verfolgt (nicht nur behauptet):** `storage_geometry.yaml` setzt `power_capex_eur_per_mw: 28.200`
(Zeile 114) für `tes_sb` (Stadtbach-TES bezieht seine Parameter von dort, nicht aus `Stadtbach_topo.yaml`s
eigenem `tes_sb`-Block, der dieses Feld gar nicht führt — "DEAD"-Kommentar in der YAML ist korrekt).
`component_assembler.py` Zeile 1442 übernimmt diesen Wert (0,0 wenn TES deaktiviert — korrekt, erklärt warum
C1/REF keinen Effekt zeigt) und reicht ihn an `GeometricStorageBlock(power_capex_eur_per_mw=...)` weiter.
`geometric_storage.py` Zeile 465-466 addiert `power_capex_eur_per_mw * cap_p` **direkt in `self._capex_raw_expr`**
— dieselbe Expression, die (Zeile 717) als `fs["capex_raw_expr"]` exportiert wird. `component_assembler.py`
Zeile 1640-1644 liest genau dieses `capex_raw_expr`, multipliziert mit `annual_factor` und hängt es an
`sys_buses.capex_terms` — das ist exakt der Term, der am Ende in `model.capex_cost_expr` (constraint_builder.py
Zeile 1120) landet, den `result_collector.py` Zeile 1019 **direkt** (nicht neu berechnet) als `Capex_cost_EUR`
ausliest. **Ergebnis: der power-CAPEX-Term ist durchgängig korrekt verdrahtet und bereits in `Capex_cost_EUR`
enthalten — er fehlt nicht.** Die im Auftrag vorgeschlagene Ursache (28.200 €/MW × 38,8 MW × (ANF 0,0651 +
O&M 0,005) ≈ 76,6 k€ ≈ Residuum) ist damit durch Code-Prüfung **nicht bestätigt** — die zahlenmäßige Nähe zum
Residuum (82.204 €) ist wahrscheinlich Zufall (anderer Ursprung, ähnliche Größenordnung).

**Weitersuchen (da nicht bestätigt, wie im Auftrag vorgesehen):** Die tatsächliche Ursache bleibt offen. Ein
belastbarer nächster Schritt wäre, `result_collector.py`s eigene residual-Berechnung (die bereits als ERROR-Log
existiert) um eine Auflistung ALLER 17 Terme mit `pyo.value(...)` direkt gegen `pyo.value(model.obj)` zu
ergänzen (Debug-Ausgabe) und an einem kleinen, schnellen Testlauf zu verifizieren — das ist ein Code-Eingriff
(B1-Kandidat), hier aber nicht autorisiert ([ ] im Auftrag) und auch nicht durch reines Lesen lösbar. **B1 bleibt
daher korrekt nicht umgesetzt.**

## A5 — Gebaute Leistungen C1/C2 (EK, Lastspitze)

**`ek_sb` ist in BEIDEN Läufen mit 0 MW gebaut** (`EK_SB_build=0.0`, `EK_SB_cap_mw=0.0`, `EK_SB_Pel`-Summe = 0
MWh/a in C1 und C2, direkt aus dem Lösungsdump verifiziert). Das erklärt, warum REPORT_v10 keine EK-Zeile zeigte
— es gab nichts zu zeigen, kein Auswertungsfehler. Damit ist der im Auftrag vermerkte Punkt "EK-Leistung fehlt
erneut" aufgelöst: sie fehlt nicht in der Analyse, sie ist tatsächlich null.

**Lastspitze Strombezug (`P_buy_peak`, Jahresmaximum von `electricity_purchase_MW`):**
- REF (C1): **0,329 MW**, Stunde 8547 (letzte Dezember-Woche). Tritt in 10 von 12 Monaten identisch auf
  (Januar-Juni, September-Dezember; Juli/August niedriger, 0,281/0,285 MW).
- S1 (C2): **2,960 MW**, Stunde 3617. Tritt in **allen 12 Monaten** identisch auf (ganzjährig bindend) —
  die TES-Ladeleistung (bis 38,8 MW thermisch) plus die größere WP (13,8 MW) erzeugen einen ganzjährig
  wiederkehrenden Lastspitzen-Moment, nicht nur ein einzelnes Jahresereignis.

**Treiber der +334.769 € Differenz (C2 vs. REF):** Aus `P_buy_peak` allein berechnet sich (bei
`demand_charge_eur_per_mw_y`=63.620 €/MW/a, egal ob Jahres- oder Monatsspitzen-Abrechnung, da der Peak
ganzjährig gleich ist): ΔDemand_charge ≈ (2,960−0,329) MW × 63.620 €/MW ≈ **167.400 €** — nur **die Hälfte**
der berichteten Differenz. Siehe v11-M2: die berichteten `Demand_charge_cost_EUR`-Werte selbst sind exakt das
Doppelte dessen, was aus `P_buy_peak` alleine folgt (für REF UND S1 gleichermaßen, Faktor 1,99999 beide Male)
— ein strukturelles, aber hier nicht abschließend geklärtes Merkmal (vermutlich zwei Demand-Charge-Zonen auf
demselben Netzanschluss). Der ÜBERGEORDNETE Treiber (größere WP + TES-Ladeleistung schaffen eine neue, jetzt
ganzjährig bindende Lastspitze) ist damit klar benannt, auch wenn der exakte 2×-Faktor offen bleibt.

## A6 — Konvergenz (C1, C2 vs. PIN0)

**Variablentypen (Gurobi, vor/nach Presolve):**

| Lauf | Binär vor Presolve | Binär nach Presolve | Δ vs. PIN0 (vor) | Δ vs. PIN0 (nach) |
|---|---|---|---|---|
| PIN0 | 1.200.133 | 275.788 | — | — |
| C1 | 1.217.644 | 301.855 | +17.511 | +26.067 (+9,45%) |
| C2 | 1.217.656 | 301.867 | +17.523 | +26.079 (+9,46%) |

Der Zuwachs vor Presolve (≈17.5k, sowohl C1 als auch C2) passt sehr genau zu **zwei neuen 8.760-stündigen
Binärfamilien**: `HKW_TO_MAN_flow_dir` (die neue bidirektionale Leitung, 8.760 Binärvariablen) **plus**
`hp_sb_on` (das Commitment der neu gebauten WP, in PIN0 bei cap=0 effektiv wegfixiert/presolved) — 2×8.760 =
17.520, beobachtet 17.511/17.523 (Restdifferenz plausibel durch Randeffekte). **TES-eigene Größenbinärs
(discrete-ladder `ysel[k]`) tragen nur ≈12 zusätzliche Binärvariablen bei (C2 vs. C1)** — vernachlässigbar
gegenüber den >1,2 Mio. Gesamtbinärs.

**Hat die bidirektionale Leitung oder die Vorwärm-Bedingung die Schranke verschlechtert?** Die REINE ANZAHL
neuer Binärs (+17,5k von >1,2 Mio., +1,46%) ist zu klein, um allein den beobachteten Konvergenz-Einbruch zu
erklären (PIN0: 0,1455% Gap in 28.419 s; C1: 0,517% in 174.052 s trotz 48h-Budget; C2: 2,121% in 174.099 s).
Qualitativ plausibler Beitrag: `flow_dir`/`m_dot_abs` werden über Big-M-Nebenbedingungen linearisiert
(`pipe_pair.py` Zeilen 258-282) — Big-M-Formulierungen sind eine bekannte Quelle loser LP-Relaxationen, unabhängig
von der reinen Variablenzahl. Die `preheat_alpha_ts`-Bedingung selbst fügt KEINE eigene Binärvariable hinzu (nur
eine stetige stündliche Kopplungsnebenbedingung), ist also als alleinige Ursache unwahrscheinlich. **Der
wahrscheinlichste Haupttreiber der schlechten Konvergenz ist aber vermutlich v11-M1 selbst**: die
Bilanzgleichung `hp_sb_Q + Q_consumer = demand + dump` mit künstlich dopplem Angebot lässt dem Solver an jedem
Zeitschritt einen großen, ökonomisch bedeutungslosen Freiheitsgrad (wie viel "Phantom-Wärme" gedumpt wird), der
die Gurobi-Heuristiken vermutlich stark beschäftigt, ohne echten Bound-Fortschritt zu bringen — das ist eine
Vermutung (Status: vermutet, nicht belegt), die sich erst nach dem v11-M1-Fix testen lässt (neuer Lauf nötig,
hier nicht autorisiert). C2 (mit TES) ist trotz nur +12 zusätzlicher Binärs deutlich schlechter konvergiert als
C1 (2,121% vs. 0,517%) — das spricht dafür, dass TES's STETIGE Variablen (Lade-/Entlade-/SOC-Trajektorien über
8.760h, kombiniert mit v11-M1) den Solver erschweren, nicht TES's eigene Größenentscheidung.

---

## Teil B — Code (nur `[x]`)

### B2 — Ergebnisarchiv-Kollisionsschutz (umgesetzt)

**Implementiert in `scripts/paper_2/scenario_runner.py`** (eigener Commit):
1. Neue Env-Var `CALION_RUN_TAG`: wenn gesetzt und `CALION_OUT_BASE` NICHT gesetzt, schreibt jeder Lauf nach
   `output/<tag>/<scenario_id>/` statt `output/paper2_runs/<scenario_id>/`. Rückwärtskompatibel (Default
   unverändert: `output/paper2_runs/`, falls weder Tag noch Base gesetzt).
2. **Kollisionsschutz:** `run_single_scenario(..., force_rerun=True)` bricht jetzt mit `RuntimeError` ab, wenn
   das Zielverzeichnis bereits ein `meta.json` (= abgeschlossener Lauf) enthält — statt es stillschweigend zu
   überschreiben. Das ist genau der Mechanismus, der v10-M1 verhindert hätte (der Verlust von
   `output/paper2_runs/SB-S1-HK0`s echtem v7-Ergebnis durch einen Build-Test unter derselben scenario_id,
   2026-10-23). Verhalten ohne `force_rerun` (Skip-Pfad) unverändert.
3. Verifiziert: (a) `CALION_RUN_TAG=v11_test` → `OUT_BASE` zeigt korrekt auf `output/v11_test`; (b) `force_rerun=True`
   auf ein bereits befülltes Verzeichnis löst den `RuntimeError` aus; (c) `force_rerun=False` auf dasselbe
   Verzeichnis liefert weiterhin den unveränderten `{"status": "skipped", ...}`-Pfad.

**Einmalige Migration (Dateisystem, kein Code):** die 6 vorhandenen v9/v10-Ausgabeverzeichnisse (die einzigen,
die in diesem Worktree unter `output/paper2_runs/` lagen) wurden verschoben, nicht gelöscht:

| Alt | Neu |
|---|---|
| `output/paper2_runs/SB-S0-HK0-PIN0` | `output/v9/SB-S0-HK0-PIN0` |
| `output/paper2_runs/MM-S0-HK0-PIN0` | `output/v9/MM-S0-HK0-PIN0` |
| `output/paper2_runs/SB-REF-HK0` | `output/v10/SB-REF-HK0` |
| `output/paper2_runs/SB-S1-HK0` | `output/v10/SB-S1-HK0` |
| `output/paper2_runs/MM-REF-HK0` | `output/v10/MM-REF-HK0` |
| `output/paper2_runs/MM-S1-HK0` | `output/v10/MM-S1-HK0` |

Inhalt nach der Migration stichprobenhaft verifiziert (meta.json lesbar, Status/Objektivwert unverändert).
**Wichtig für künftige Läufe:** jeder `CALION_WARMSTART_FROM`-Pfad, der auf die alten `output/paper2_runs/...`-
Pfade dieser 6 Läufe zeigt, muss auf die neuen `output/v9/...`/`output/v10/...`-Pfade angepasst werden.
`output/paper2_runs/` selbst bleibt als (jetzt leerer) Default-Pfad für ungetaggte Läufe bestehen.

### B1, B3 — nicht umgesetzt (korrekt, kein `[x]`)

B1 (fehlende Kostenzeile): A4 bestätigt die vorgeschlagene Ursache nicht — kein Fix ohne bestätigte Ursache.
B3 (Festauslegungs-Modus `CALION_FIXED_DESIGN`): nicht markiert, nicht umgesetzt.

---

## Teil C — Läufe

**Kein Punkt in Teil C ist mit `[x]` markiert** (C1 Laufzeittest Festauslegung: `[ ]`; C2 Enumerationsplan: `[ ]`).
Zusätzlich hat der Nutzer in diesem Auftrag explizit angewiesen, vorerst **keine neuen Läufe zu starten** ("plane
das alles schonmal aber noch keine neuen Runs starten in einer anderen session rechnen wir schon und der server
ist sehr ausgelastet"). Beide Signale stimmen überein: **Teil C wurde nicht ausgeführt.**

Vorbereitender Hinweis für einen künftigen Auftrag: B3 (Festauslegungs-Modus) ist eine Voraussetzung für C1/C2
und selbst nicht autorisiert — ein künftiger C1-Testlauf kann erst stattfinden, nachdem B3 implementiert UND
freigegeben ist. Außerdem sollte **v11-M1 vor jedem weiteren Investitions-Lauf mit WP an j_man behoben werden**
— sonst wiederholt ein Festauslegungs-Lauf, der C1s (fehlerhaftes) Design fixiert, exakt denselben
Doppelzählungs-Fehler, nur ohne die Möglichkeit, die WP-Größe noch zu korrigieren.

---

## Zusammenfassung / Priorisierung für den nächsten Auftrag

1. **v11-M1 (Bilanzfehler j_man) zuerst beheben** — ohne diesen Fix sind C1 und C2 aus v10 (und jeder künftige
   Lauf mit WP an einem sekundären Mischknoten mit bidirektionaler Zuleitung) nicht interpretierbar.
2. Danach C1/C2 (und ggf. C3/C4 aus v10, die mit TES-Standort j_hkw arbeiten) neu lösen.
3. v11-M2 (Demand-Charge-2×-Faktor) und v10-M2 (82.204-€-Residuum) bleiben offene, kleinere Nebenbefunde —
   lohnen sich für eine gemeinsame Debug-Instrumentierungsrunde, sind aber nicht blockierend für den Hauptbefund.
4. B3 (Festauslegungs-Modus) erst NACH v11-M1s Fix sinnvoll umsetzen und testen.
