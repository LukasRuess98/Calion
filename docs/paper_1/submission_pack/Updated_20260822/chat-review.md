# Review der Overleaf-Fassung und der Reviewer-Antworten

Stand der Prüfung: 20. August 2026  
Primär geprüfte Fassung: `submission_pack/overleaf/`  
Vergleichs-/Kontextmaterial: alte Draft-/Build-Fassungen, FHG-Korrekturdokument, Reviewer-Mail, bisheriger Response Letter sowie `zenodo_paper_1/` einschließlich Code, Konfigurationen, CSV-Ergebnissen und Abbildungen.

## Kurzurteil

Die Überarbeitung ist konzeptionell deutlich besser als die alte Fassung, aber **noch nicht einreichungsreif**. Besonders überzeugend ist die exakte Vier-Kontroll-Decomposition von Verlust- und Topologieeffekt. Mehrere zentrale Aussagen zu Validierung, Regret, Nichtlinearität und Transportverzögerung gehen jedoch über das hinaus, was Code und freigegebene Ergebnisse tatsächlich belegen. Außerdem bestehen sichtbare LaTeX-Referenzfehler, Einheitenfehler, widersprüchliche Zahlen, eine nicht reproduzierbare Release-Struktur und eine inhaltlich noch unzutreffende Reviewer-Antwort.

Die wichtigsten Blocker sind:

1. Die angegebene Abweichung von 1,2 % validiert den **jährlichen Wärmebedarf**, nicht den jährlichen Netzverlust.
2. Der fehlgeschlagene stündliche Energy-Balance-Test ist ein interner Modell-/Export-Widerspruch und kein Messdatenproblem bei kleiner Last.
3. Der sogenannte Decision Regret ist keine physisch re-dispatchte Ausführung; die +46,1 % sind im Wesentlichen eine monetäre Bewertung zusätzlicher Verluste.
4. Der Solver-Objective-Residual ist nicht konstant und hebt sich zwischen den vier Kontrollen nicht vollständig auf.
5. Die behauptete Modellleiter stimmt nicht mit den tatsächlich optimierten bzw. nur vorwärts ausgewerteten Modellen überein.
6. Die Beschreibung der nichtlinearen Physik stimmt teilweise nicht mit der Implementierung überein.
7. Die Transportverzögerung von L6 wird im MILP-Code übersprungen; die behauptete isolierte Delay-Stufe ist damit nicht nachgewiesen.
8. Der Temperatur-Validierungsanhang widerspricht der neuen, vorsichtigeren Validierung im Haupttext.

## Schutzumfang dieser Prüfung

Auf ausdrücklichen Wunsch wurden **keine Manuskript-, Ergebnis-, Code-, Release- oder Korrespondenzdateien geändert**. Erstellt wurde ausschließlich diese Datei `chat-review.md`. Alle nachfolgenden Punkte sind Änderungsvorschläge, keine bereits vorgenommenen Änderungen.

## Priorität P0 – vor Einreichung zwingend zu klären

### P0.1 – Die 1,2-%-Zahl ist keine Validierung des jährlichen Netzverlusts

**Befund**

Der Validierungsrunner vergleicht die gemessene Spalte `Waermebedarf_MWth` mit dem exportierten `Q_demand_total_MW`. Die freigegebene KPI-Datei enthält:

- gemessene Jahreswärme: 9.895,2746 MWh,
- simulierte Jahreswärme: 9.773,9087 MWh,
- relative Abweichung: 1,2265 %.

Damit ist höchstens die jährliche Größenordnung der **Nachfrageenergie** geprüft. Daraus folgt nicht, dass der jährliche Netzverlust gemessen oder auf 1,2 % validiert wurde. Für eine Verlustvalidierung wären zumindest gemessene Einspeiseenergie und gemessene Abgabeenergie auf konsistenten Systemgrenzen nötig; deren Differenz wäre anschließend noch gegen Speicher- und Messgrenzen abzugrenzen.

**Betroffene Aussagen**

- `submission_pack/overleaf/main.tex`, ungefähr Zeilen 446 und 487: jährlicher Netzverlust sei auf etwa ein Prozent abgeglichen bzw. thermisch/hydraulisch verankert.
- `submission_pack/overleaf/validation_protocol_v2.tex`, ungefähr Zeile 33: gelieferte Jahresenergie und „hence annual network loss“.
- `submission_pack/overleaf/validation_results_v2.tex`, ungefähr Zeile 54: Messungen würden den Jahresverlust auflösen.
- `submission_pack/02_correspondence/response_letter.md`: insbesondere Antworten zu R2.3/R2.4 mit der Behauptung eines gemessenen Jahresverlusts von 1,2 %.

**Erforderliche Korrektur**

- Alle Aussagen „annual network loss validated/matched to 1.2 %“ entfernen.
- Zulässige Formulierung: Die jährliche aggregierte Nachfrageenergie stimmt innerhalb von 1,23 % überein; dies ist ein Plausibilitätscheck der Energieskala, keine unabhängige Verlustvalidierung.
- Falls eine echte Verlustvalidierung möglich ist: Systemgrenzen, Einspeisung, Abgabe, Speicherterm, zeitliche Aggregation, Messunsicherheiten und berechneten Messverlust explizit dokumentieren und als neue KPI ausgeben.
- Reviewer R2.4 bis dahin nur als **teilweise erfüllt** bezeichnen.

**Mögliche Ersatzformulierung**

> The annual measured demand energy and the exported demand series agree within 1.23%. This check supports the annual energy scale but does not independently validate annual network losses, because consistent measured supply-side energy and storage-boundary data are unavailable.

### P0.2 – Der fehlgeschlagene Energy-Balance-Test ist intern und darf nicht mit einem kleinen Messwert-Nenner erklärt werden

**Befund**

`zenodo_paper_1/tools/validation_runner.py` berechnet im Energy-Balance-Check Erzeugung minus Nachfrage, Netzverlust, Speicherladung/-entladung und gegebenenfalls Dump. In diesem Test werden keine Messwerte verwendet. Trotzdem wird das Ergebnis im Manuskript als erwartete Abweichung in Niedriglaststunden mit problematischem relativem Nenner erklärt.

Freigegebene KPIs:

- mittlere relative Abweichung: 6,4094 %,
- maximale relative Abweichung: 98,8051 %,
- Gate `<= 2 %`: nicht bestanden.

Zusätzliche Prüfung von `zenodo_paper_1/results/L3/dispatch_hourly.csv`:

- signierte Jahresdifferenz: −1.767,534 MWh,
- Summe der absoluten stündlichen Differenzen: 1.767,534 MWh,
- bezogen auf die Nachfrage: 18,0801 %,
- maximale stündliche Differenz: 5 MW,
- 8.404 Stunden schließen exakt,
- 351 Stunden weisen exakt −5 MW auf; fünf weitere Stunden haben kleinere Abweichungen.

Das sehr diskrete Muster von wiederholt genau −5 MW deutet eher auf eine nicht exportierte oder falsch zugeordnete 5-MW-Komponente hin, beispielsweise Speicherladung/-entladung oder einen Exportzustand. Es beweist nicht, dass der Optimierer selbst unzulässig ist, zeigt aber einen **ungeklärten Modell-/Export-/Bilanzierungsfehler**.

**Widersprüche im Text**

- `validation_protocol_v2.tex` verspricht stündliche Bilanzschließung bis zur Maschinenpräzision.
- `validation_results_v2.tex` zeigt ein gescheitertes Gate, erklärt dies anschließend aber als Niedriglast-/Nennerproblem.
- Diese Erklärung ist unzulässig, weil die zugrunde liegende Differenz eine interne Energiebilanz ist und keine Messwertabweichung.

**Erforderliche Korrektur**

- Root Cause im Export bzw. in der Bilanzformel ermitteln.
- Nach Korrektur L3 neu exportieren und den Test erneut ausführen.
- Zusätzlich absolute Kennzahlen ausgeben: Jahresresiduum, Summe absoluter stündlicher Residuen, Maximum in MW, Zahl der Stunden oberhalb einer absoluten Toleranz.
- Erst nach bestandener interner Bilanz Aussagen zur externen Validierung treffen.
- Falls der Fehler nur den Export betrifft, dies transparent dokumentieren und nachweisen, dass die Solver-Bilanzrestriktionen im tatsächlichen Modell schließen.

### P0.3 – „Decision regret“ ist derzeit keine physische Ausführung oder Recourse-Simulation

**Befund**

In `zenodo_paper_1/tools/evaluator.py` wird der vorhandene wirtschaftliche Kostenwert um

- `max(total_loss - loss_assumed, 0)` multipliziert mit einem festen marginalen Wärmepreis und
- zusätzliche Pumpkosten

erhöht. Der Code verteilt die fehlende Wärme nicht stündlich auf konkrete Anlagen, prüft keine freie Erzeugungskapazität, aktualisiert keinen Speicherzustand, repariert keinen Dispatch und berechnet keine unversorgte Wärme.

`regret_decomp.csv` bestätigt diese Interpretation: Für CP beträgt die zusätzliche Verlustenergie etwa 1.159,461 MWh; gleichzeitig sind alle ausgewiesenen Zähler physischer Verletzungen null. Die Sensitivitätsdatei verändert den monetären Wärmepreis, nicht die physische Recourse-Logik.

**Nicht belegte oder überzogene Formulierungen**

- „executed schedule“ bzw. tatsächlich ausgeführter Fahrplan,
- Deckung durch die marginale/Spitzenlastanlage in den jeweiligen Winterstunden,
- „physically undeliverable“,
- „incompetent controller“,
- behauptete physische Lieferfähigkeit bzw. deren Verletzung,
- die Aussage, der Controller müsse die konkreten Verlustmengen in realen Stunden nachfahren.

**Erforderliche Entscheidung**

Variante A – methodisch stärker:

- echten stündlichen Recourse implementieren,
- den ursprünglichen Fahrplan mit Referenzverlusten prüfen,
- stündliche Fehlwärme ermitteln,
- verfügbare Anlagenleistung und Rampen, Speicherzustand und Speichergrenzen berücksichtigen,
- Spitzenlast-/Marginalanlage explizit zuweisen,
- unversorgte Energie, maximale Unterdeckung, Zahl betroffener Stunden und Recourse-Kosten berichten.

Variante B – ohne neuen Recourse-Lauf:

- die Analyse umbenennen, z. B. in „forward-valued loss shortfall“ oder „reference-model valuation of omitted losses“,
- deutlich sagen, dass es sich um eine monetäre Bewertungsrechnung und nicht um einen reparierten physischen Dispatch handelt,
- alle Aussagen zu physischer Undeliverability, konkreter Spitzenlastdeckung und Controller-Inkompetenz entfernen,
- die +46,1 % nur als konservative/preisabhängige Bewertungsgröße unter der festgelegten Marginalpreisannahme präsentieren.

**Mögliche Ersatzformulierung**

> The reported 46.1% increase is a forward valuation of additional reference-model heat losses at an assumed marginal heat price. It is not a chronological redispatch and therefore does not establish physical infeasibility or identify the unit that would cover the shortfall.

### P0.4 – Der Objective-Residual hebt sich nicht vollständig auf

**Befund**

Die Solver-Zielfunktion enthält neben den später berichteten wirtschaftlichen Kosten weitere Terme, unter anderem Brutto-CO2- und Speicherzyklierungsanteile. Die postprozessierte Kennzahl `economic_cost` bildet diese Terme nicht identisch ab.

Aus `objective_decomposition.csv`:

- CP-Residual: ca. 80.443,18 EUR,
- CP+L-Residual: ca. 86.214,06 EUR,
- ND0-Residual: ca. 80.332,38 EUR,
- L1-Residual: ca. 86.084,54 EUR.

Die Residualänderung von CP zu L1 beträgt somit ungefähr 5.641,36 EUR. Der Residual ist weder klein noch für alle vier Kontrollen konstant. Die Aussage, er hebe sich in allen Bias-/Regret-Differenzen auf, ist daher falsch.

Die wirtschaftliche Vier-Kontroll-Zerlegung ist algebraisch korrekt:

- Gesamt-Gap: 20.591,262 EUR,
- Verlustanteil: 19.736,620 EUR = 95,8495 %, gerundet **95,8 %**,
- Topologieanteil: 961,299 EUR = 4,6685 %, gerundet 4,7 %,
- Interaktion: −106,657 EUR = −0,5180 %, gerundet −0,5 %.

Auf Basis der Solver-Zielfunktion ergibt sich dagegen ungefähr:

- Gesamt: 26.232,62 EUR,
- Verlust: 25.507,50 EUR = 97,24 %,
- Topologie: 850,50 EUR = 3,24 %,
- Interaktion: −125,38 EUR = −0,48 %.

Die qualitative Aussage „Verluste dominieren“ bleibt robust. Die exakte Zahl 95,8 % ist jedoch an die nachgelagerte wirtschaftliche Kostenmetrik gebunden und darf nicht als invariant gegenüber der Zielfunktionsdefinition dargestellt werden.

**Erforderliche Korrektur**

- Behauptungen „near-constant residual“, „cancels in every difference“ und gleichartige Aussagen in `cost_accounting_v2.tex`, `tab_objdecomp.tex` und dem Response Letter entfernen.
- Klar zwischen Optimierungsziel und nachgelagerter Kostenmetrik unterscheiden.
- Bevorzugt die vier Kontrollmodelle mit einer Zielfunktion neu rechnen, die exakt der berichteten wirtschaftlichen Kostenmetrik entspricht.
- Alternativ beide Zerlegungen transparent berichten und die 95,8 % als metric-specific bezeichnen.
- Die tatsächlichen Regularisierungs-/Strafterme in der mathematischen Zielfunktion vollständig aufführen.

### P0.5 – Modellanzahl, Modellleiter und Behandlungstypen sind widersprüchlich

**Befund**

`main.tex` spricht von „five formulations“, führt aber CP, CP+L, ZN, ND0, L1–L6 und NL ein. Gleichzeitig wird eine monotone Leiter behauptet, bei der je Stufe genau ein Phänomen ergänzt werde. Tatsächlich sind die Behandlungstypen gemischt:

- optimiert: CP, CP+L, ND0, L1, L3 und offenbar L6,
- nur vorwärts ausgewertet: L2, L4, L5,
- NL: vorwärts ausgewertet und zusätzlich zwei kurze Fixed-Binary-Temperatur-Reoptimierungen,
- ZN: Aggregations-/Clustering-Sensitivität.

L4 ergänzt zudem nicht nur ein einziges Phänomen, sondern Stationsauflösung, Lateralen und damit zusammenhängende Verlust-/Pumpanteile. Bei Übergängen von optimierten zu nur ausgewerteten Stufen ändert sich außerdem die Behandlung selbst.

Die synthetische Studie wird als dieselbe Leiter mit verteiltem Erzeugungsfaktor dargestellt. Die tatsächliche 135-Fall-Struktur ist jedoch 3 Netzknotenvarianten × 5 Längen × 3 Heterogenitätsstufen × 3 Speichergrößen; die Erzeugung ist zentral. Die synthetischen Outputs verwenden im Wesentlichen die vier Decomposition Controls, nicht die vollständige L1–L6-Leiter.

**Empfohlene konsistente Taxonomie**

1. **Decomposition controls, independently optimized:** CP, CP+L, ND0, L1.
2. **Additional optimized reference variants:** L3 und – nur falls technisch gültig – L6.
3. **Forward-evaluated extensions:** L2, L4, L5.
4. **Nonlinear reference evaluation:** native forward evaluator plus zwei 72-h Fixed-Binary-Temperaturfenster.
5. **Aggregation sensitivity:** ZN.

**Erforderliche Korrektur**

- „five formulations“ korrigieren.
- Nicht mehr alle Modelle als monotone, unabhängig optimierte Leiter darstellen.
- In jeder Tabelle explizit `optimized`, `forward-evaluated`, `fixed-binary re-optimized` oder `sensitivity` angeben.
- Die Aussage „one phenomenon per step“ stark einschränken oder entfernen.
- Synthetisches Design korrekt als 3×5×3×3 beschreiben und den nicht vorhandenen Distributed-Generation-Faktor entfernen.

### P0.6 – Beschreibung der Nichtlinearität stimmt nicht mit dem Code überein

**Befund**

`extended_physics_v2.tex` beschreibt unter anderem:

- eine exponentielle Temperaturfortpflanzung als L2-PWL/Taylor-Formulierung,
- native quadratische Druckverluste in NL,
- native kubische Pumpenleistung in NL.

In `zenodo_paper_1/calion/models/blocks/pipe_pair.py` ist die Implementierung anders:

- Bei `temperature_linearize=True` werden Temperaturen als Parameter fixiert und der Verlust über `UL(T-T_ground)` berechnet.
- Bei `False` wird die Temperaturabhängigkeit zusammen mit der bilinearen Enthalpiebeziehung wieder aktiviert.
- Druckverlust und Pumpenleistung bleiben in den Optimierungsmodellen dreisegmentig stückweise linear; ein nativer quadratischer/kubischer NL-Optimierungszweig ist nicht erkennbar.
- Der Forward Evaluator verwendet dagegen native exponentielle Temperaturfortpflanzung und berechnete hydraulische Beziehungen.

Die zwei sogenannten „weekly“ Vergleiche sind tatsächlich 72-Stunden-Fenster:

- Winter: 13.–15. Januar,
- Herbst: 14.–16. Oktober.

Ergebnisse:

- Winter: MILP 9.511,2595; native 9.497,4097; Lower Bound 9.496,6026; Gap 0,0085 %; Incumbent-Differenz −0,1456 %.
- Herbst: MILP 4.260,3254; native 4.246,2218; Lower Bound 4.245,1512; Gap 0,0252 %; Incumbent-Differenz −0,3310 %.

Diese Läufe isolieren bei fixierten Binärentscheidungen die Temperaturbehandlung in zwei 72-h-Fenstern. Sie belegen weder den Jahresfehler noch den Gesamtfehler aller PWL-Approximationen und sind keine vollständige nichtlineare Reoptimierung aller Entscheidungen.

**Erforderliche Korrektur**

- „weeks“ durch „72-hour windows“ ersetzen.
- Präzise sagen, dass Binärentscheidungen fixiert sind und nur die Temperaturbehandlung verglichen wird.
- „true physics“, „fully nonlinear optimum“ und Aussagen über den gesamten PWL-Fehler entfernen.
- Druck- und Pumpenmodell im Text an die tatsächliche Implementierung anpassen.
- R1.3/R2.3 nur als teilweise erfüllt darstellen.

### P0.7 – Die Transportverzögerung von L6 ist im MILP nicht implementiert

**Befund**

In `pipe_pair.py` wird die Transportverzögerung im MILP-Pfad explizit übersprungen; die gelieferte Wärme wird direkt verknüpft. Eine dreistufige Delay-Approximation wirkt nur im nichtlinearen Modus. Damit ist die Gleichheit von L6 und L3 kein Nachweis dafür, dass alle Laufzeiten kleiner als eine Stunde sind oder `k=0` gilt. Sie kann schlicht daraus folgen, dass im MILP keine Verzögerung angewendet wurde.

Zusätzliche Inkonsistenzen:

- Aktuelle T2P6-Konfigurationen sind im Release nicht vollständig enthalten.
- `computation_meta.csv` nennt T2P6, aber die passende Konfiguration fehlt.
- Ältere Pipe-Exporte weisen teilweise `k_p_steps=3` aus, was der Erzählung eines überall verschwindenden Delays widerspricht.

**Erforderliche Korrektur**

- Entweder einen echten stündlichen Delay im MILP implementieren, kontrolliert testen und L6 neu rechnen,
- oder L6 als isolierte gelöste Stufe entfernen und offen angeben, dass Transportverzögerung in der optimierten Vergleichsleiter nicht implementiert wurde.
- Keine `k=0`-Behauptung ohne aus den aktuellen Rohrdaten reproduzierbare Laufzeit-/Diskretisierungsberechnung.

### P0.8 – Der Temperatur-Validierungsanhang ist widersprüchlich und offenbar veraltet

**Befund**

`appendices_optional_v2.tex` enthält einen sichtbaren Abschnitt „Per-node temperature error breakdown“ mit sechs Validierungsknoten, mittlerem Winter-MAE von 1,32 K und All-node-MAE von 1,68 K. Der Haupttext erklärt dagegen, dass ein sauberer Held-out-Split wegen Mischventilen nicht möglich ist. Die aktuelle `validation_kpis.json` weist für den Far-End-Knoten ein MAE von 9,21 K aus; außerdem enthält der Export keine fortgepflanzte Trunk-Temperaturabnahme.

Der Anhangskommentar selbst deutet an, dass die Kategorisierung problematisch ist. In sichtbarer Form darf die Tabelle nicht stehen bleiben.

**Erforderliche Korrektur**

- Tabelle und Verweis entfernen, falls keine aktuelle, vollständig rückverfolgbare Ausgabedatei existiert.
- Alternativ Messpunkte, Split-Logik, Modelloutput, Zeitraum, Stichprobenzahl und Erzeugungsskript bereitstellen und die Zahlen neu generieren.
- Den Verweis in `validation_results_v2.tex` entsprechend korrigieren.

## Priorität P1 – wichtige fachliche und numerische Korrekturen

### P1.1 – Die FHG-Korrektur 81,2 % → 67,4 % ist sachlich falsch

`zenodo_paper_1` enthält in `fidelity_rule.csv` einen Maximalwert von `b_meas_pct = 81,216562 %`; der maximale Verlustfaktor liegt bei ungefähr 1,7489. Die 67,4-%-Änderung beruht offenbar auf einer Verwechslung verschiedener Definitionen. `b_pred = lambda/(1+lambda)` erreicht etwa 63,62 %, ist aber nicht dieselbe Größe wie der modellbasierte gemessene Kostenburden.

- `tab_decomposition.tex` ist mit 3,2–81,2 % konsistent.
- `main.tex`, ungefähr Zeilen 766–780, nennt fälschlich 67,4 % und enthält einen Kommentar, es gäbe keinen Wert von 81,2 %.
- `F_rule` begrenzt die y-Achse auf 75 % und schneidet dadurch reale Datenpunkte bis 81,2 % ab.
- `F_drift` zeigt visuell ebenfalls Werte um 81 % und bestätigt damit die CSV.

**Vorschlag:** 81,2 % wiederherstellen und die Achsengrenze mindestens auf 85 % setzen. Alternativ die Metrik bewusst neu definieren, dann aber Tabelle, Formel, Text und Abbildung vollständig konsistent neu erzeugen.

### P1.2 – Out-of-sample-Zahlen sind im Fließtext falsch

`prediction_oos_summary.csv` berichtet:

- Held-out MAPE: 19,0 %,
- MAE: 13,3 Prozentpunkte,
- 30-km-Fall: tatsächlich 61 %, vorhergesagt 54 %, Fehler 7 Punkte,
- 50-km-Fall: tatsächlich 73 %, vorhergesagt 54 %, Fehler 20 Punkte.

`main.tex` spricht noch von „within a couple of points“ und 14 %. Das muss zu 7 Punkten bzw. 19 % korrigiert werden. Die Güte ist nützlich, aber nicht so hoch, dass die Regel als präzise Entscheidungsgrenze dargestellt werden sollte.

### P1.3 – 95,8 % und 95,9 % vereinheitlichen

Aus den aktuellen wirtschaftlichen Kosten ergibt sich 95,849491 %. Bei üblicher Rundung auf eine Dezimalstelle ist das **95,8 %**, nicht 95,9 %. `tab_gap_stability.tex`, `tab_robustness.tex` und der Response Letter verwenden teilweise 95,9 %. Alle Stellen auf eine gemeinsame Datenquelle und Rundungsregel bringen. Falls unterschiedliche Solver-Läufe gemeint sind, diese mit Run-ID und Kostenwerten getrennt kennzeichnen.

### P1.4 – Caption von `F_regret` beschreibt eine andere Grafik

Die aktuelle Abbildung ist ein gruppiertes Balkendiagramm mit sieben Modellstufen. Die Caption in `main.tex` beschreibt dagegen eine Bias=Regret-Diagonale, Scatterdarstellung und ein Inset. Caption vollständig an die tatsächlich eingebundene Abbildung anpassen oder die beabsichtigte Abbildung reproduzierbar neu erzeugen.

### P1.5 – Die Fidelity Rule ist ein Heuristik-/Screeninginstrument, kein parameterfreier Entscheidungsbeweis

Die Schwellen 0–10 %, 10–30 % und >30 % sind in `figgen_p1_v2.py` fest codiert. Sie folgen nicht aus einer validierten Klassifikationsoptimierung. Ein R² von ungefähr 0,87 und ein MAE von 6,7 Prozentpunkten rechtfertigen eine nützliche Trendregel, aber nicht die Aussage, die Formel entscheide verlässlich zwischen Copperplate, Loss Adder und Nodal Model.

Zusätzlich ist „measured burden“ irreführend: Der Burden ist aus Modellergebnissen berechnet, nicht empirisch gemessen.

**Vorschlag:** Als empirische Screening-Heuristik innerhalb der untersuchten parametrischen Netzfamilie bezeichnen; Schwellen als illustrative bands kennzeichnen; externe Validierung ausdrücklich offenlassen.

### P1.6 – Vorwärts ausgewertete Vorlauftemperatur ist nicht „cost-optimal“

Die in `tab_tsup` ausgewiesenen 17,5 K sind das günstigste **feasible evaluated grid point** einer Sensitivitätsrechnung. Die Vorlauftemperatur wurde nicht gemeinsam mit dem Dispatch optimiert. Deshalb „cost-optimal supply temperature“ durch „lowest-cost feasible evaluated temperature offset“ oder eine gleichwertige Formulierung ersetzen.

### P1.7 – „Extended physics leaves dispatch decisions unchanged“ ist nicht belegt

L4 und L5 werden nur vorwärts ausgewertet. Eine Vorwärtsbewertung eines bestehenden Fahrplans kann nicht zeigen, ob eine Reoptimierung mit dieser Physik andere Entscheidungen gewählt hätte. Zulässig ist lediglich: Die nachgelagerte Kostenbewertung ändert sich unter den geprüften Annahmen wenig. Aussagen über unveränderte optimale Dispatchentscheidungen entfernen.

### P1.8 – Hydraulische Effekte sauber trennen

Der optimierte Übergang L1→L3 zeigt ungefähr +1,4 % für die hinzugefügte Trunk-Hydraulik. Zusätzliche Stations-/Lateralanteile liegen in Vorwärtsbewertungen unter 1 %. Diese Ergebnisse dürfen nicht zu einer einzigen Aussage „hydraulics are below 1 %“ zusammengezogen werden.

### P1.9 – Absolute/universelle Null-Mechanismus-Aussagen einschränken

Der letzte Absatz von `physics_null_mechanisms_v2.tex` erklärt sinngemäß, die Verlustdominanz brauche keine Qualifikation und hänge nicht von Annahmen ab. Das widerspricht direkt der Scope-Kritik von Reviewer 1. Korrekte Aussage: Unter den untersuchten Preis-, Last-, Temperatur-, Netz- und Erzeugungsannahmen ist die Verlustdominanz robust; andere Erzeugungstopologien, höhere Strom-/Pumpkosten, variable COPs und andere Betriebsgrenzen können das Verhältnis verändern.

### P1.10 – Synthetische Aussagen präzisieren

„The same holds across the synthetic factorial“ ist zu pauschal. Median, Interquartilsbereich, Minimum/Maximum und Ausnahmen angeben. Insbesondere darf aus einer zentral erzeugten synthetischen Familie nicht auf verteilte Erzeugung verallgemeinert werden.

### P1.11 – Unangemessene bzw. unpräzise Terminologie

- Titel: „Industrial“ großschreiben.
- `main.tex`, ungefähr Zeile 794: Doppelpunkt am Satzende `measured..` korrigieren.
- „incompetent controller“ durch neutralen technischen Ausdruck ersetzen.
- „true cost“/„true physics“ durch „reference-model cost“/„native forward evaluation“ ersetzen.
- „Zeroth“ stilistisch überarbeiten.
- „a-priori“ zu „a priori“ oder „prior to optimization“.
- „measured burden“ zu „model-derived cost burden“.

## Priorität P1 – mathematische Formulierung und Einheiten

### P1.12 – Falscher Gleichungsverweis

`base_formulation_v2.tex`, ungefähr Zeile 49, verweist auf `eq:pumppower`; definiert ist `eq:pump_power`.

### P1.13 – Pumpenleistungsformel fehlt der MW-Faktor

In `extended_physics_v2.tex` liefert

`m_dot * Delta p / (rho * eta)`

bei SI-Einheiten Watt. Wenn das Symbol in MW geführt wird, muss durch `10^6` dividiert oder die Einheitenkonvention explizit anders definiert werden.

### P1.14 – Wärmekapazität/Massenstrom ist einheiteninkonsistent

Die Beziehung `m_dot = Q/(c_p Delta T)` ist nur ohne weiteren Faktor konsistent, wenn `Q` und `c_p` zueinander passend skaliert sind. Die Nomenklatur nennt `c_p` in J/(kg K); die Implementierung verwendet sinngemäß 4,186 kJ/(kg K) und einen `/1000`-Faktor für MW. Gleichung, Nomenklatur und Codekonvention müssen dieselbe Einheit verwenden.

### P1.15 – Emissionsvariable ist als Tonnen beschriftet, Gleichung liefert Kilogramm

`MWh × kg/MWh` ergibt kg. Die Zielfunktion teilt später durch 1000. Deshalb `E` in der Nomenklatur als kg führen oder die Gleichung direkt in Tonnen formulieren.

### P1.16 – Druck-PWL-Gleichung entspricht weder den Einheiten noch dem Code

Die publizierte Form `sum m_k w_k` multipliziert Steigungen mit einer dimensionslosen Gewichtung und stimmt nicht mit der Codeform Segmentsteigung × Durchfluss plus Segmentinterzept × Binärvariable überein. Gleichung anhand der tatsächlichen Implementierung neu schreiben und alle Segmentvariablen/Bounds definieren.

### P1.17 – Optimierungsziel ist unvollständig dokumentiert

Die Grundformulierung nennt nicht alle tatsächlich optimierten Zusatz-/Regularisierungsterme, insbesondere Speicherzyklierung. Wenn diese Terme die Lösung beeinflussen, gehören sie in die Zielfunktionsgleichung und in die Kostenüberleitung. Andernfalls ist die berichtete Zielfunktion nicht die tatsächlich gelöste.

## Priorität P1 – LaTeX-, Verweis- und Tabellenfehler

Bei einer statischen Labelprüfung wurden keine doppelten Labels, aber folgende fehlende/vertauschte Referenzen gefunden:

| Datei/Stelle | Aktueller Verweis | Vermutlich korrekt |
|---|---|---|
| `base_formulation_v2.tex`, ca. 49 | `eq:pumppower` | `eq:pump_power` |
| `main.tex`, ca. 295 | `subsec:zonesens` | `subsec:clustering` |
| `tab_design_grid.tex`, ca. 19 | `subsec:zonesens` | `subsec:clustering` |
| `main.tex`, ca. 325 | `subsec:subsec:decision_regret` | `subsec:decision_regret` |
| `main.tex`, ca. 725 | `subsec:extended` | `sec:extended` |
| `nomenclature_v2.tex`, ca. 35 | `sec:zone` | `subsec:clustering` |
| `nomenclature_v2.tex`, ca. 122 | `app:hi` | `app:hi_definition` |

Weitere Punkte:

- `tab_val_targets.tex` enthält in einer sichtbaren Statusspalte noch Platzhalter `<? >`; alle Statuswerte müssen gesetzt und fachlich neu klassifiziert werden.
- `references.bib` nutzt für `ruess_2026_calion` den Typ `@software`, den der vorhandene Elsevier-BibTeX-Stil nicht unterstützt. Zu `@misc` oder einem vom Journalstil unterstützten Typ wechseln.
- Der DOI-Eintrag enthält offenbar ein nachgestelltes Leerzeichen.
- Im alten Build-Log steht eine 117-pt-Overfull-Box sowie mehrere Hyperref-Warnungen zu leeren Anchors. Da Log/Aux nicht sicher zur aktuellen Quelle gehören, ist ein sauberer Overleaf-Neubuild zwingend.
- Die Quelle enthält noch zahlreiche interne Autor-Kommentare/TODOs. Sie sind nicht sichtbar, sollten aber aus einem sauberen Submission Bundle entfernt bzw. klar archiviert werden.
- Nicht eingebundene Stub-Dateien wie `tab_cases.tex` und `tab_hydraulic_val.tex` enthalten noch TODO-Platzhalter. Entweder vervollständigen oder nicht in das finale Upload-Paket aufnehmen.

## Audit der FHG-Handkorrekturen

### Korrekt bzw. sinnvoll übernommen

- Der Interaktionsterm von −0,5 % wurde in Abstract/Conclusion wieder aufgenommen.
- Der Abstract ist jetzt ein Absatz.
- Die Conclusion hat keine Unterüberschriften mehr.
- Ein separater Pumpkosten-Term wurde aus der Kostenrechnung entfernt; Pumpstrom läuft über die Elektrizitätsbilanz. Damit scheint die frühere Doppelzählung behoben.
- Der Speicherexponent wurde korrigiert.
- Die pauschale Stations-Upper-Bound-Behauptung wurde zurückgenommen.
- Scope- und Distributed-Generation-Limitierungen wurden teilweise ergänzt.

### Nur teilweise oder inkonsistent übernommen

- 14 % wurde in einer Tabelle zu 19 % korrigiert, im Fließtext aber nicht durchgehend.
- 95,9 % wurde teilweise zu 95,8 % korrigiert, andere Tabellen und der Response Letter sind noch inkonsistent.
- Die Nichtlinearitätsanalyse wird weiter als Wochenanalyse bzw. vollständige native Physik beschrieben, obwohl es zwei 72-h-Fixed-Binary-Temperaturfenster sind.
- Die FHG-Anforderung nach realen Recourse-Größen – betroffene Stunden, maximale Fehlleistung, tatsächlich eingesetzte Anlage, Speicherzustand – wurde nicht erfüllt.
- Die im FHG-Dokument angesprochenen Taxonomie-, Validierungs-, Objective- und Synthetic-Design-Probleme bestehen weitgehend fort.

### Falsch übernommen

- Die Änderung 81,2 % → 67,4 % widerspricht der aktuellen freigegebenen CSV und den Abbildungen. Diese Änderung sollte rückgängig gemacht werden, sofern nicht bewusst eine neue Metrik definiert und vollständig neu ausgewertet wird.

## Erfüllung der Reviewer-Kommentare

| Kommentar | Status | Bewertung und noch offene Arbeit |
|---|---|---|
| R1.1 – Scope/Generalisierung | **Teilweise erfüllt** | Titel, Abstract und Limitationen sind vorsichtiger. Universal klingende Null-Mechanismus-Aussagen, die unvalidierten Screening-Schwellen und die fälschlich als verteilt beschriebene synthetische Erzeugung bleiben. |
| R1.2 – Accuracy vs sensitivity | **Teilweise bis weitgehend erfüllt** | Terminologie wurde verbessert. Das Referenzmodell ist aber nicht empirisch vollständig validiert, und die Decision-Regret-Analyse wird als physische Ausführung überinterpretiert. |
| R1.3 – Konfundierung von Delay/Linearisation | **Nicht vollständig erfüllt** | Stufen und zwei Vergleichsfenster wurden ergänzt. L6-Delay wird im MILP jedoch übersprungen; die 72-h-Läufe prüfen nur Temperatur bei fixierten Binärvariablen, nicht alle Linearisationen. |
| R1.4 – Validation vor Anlagenupgrade | **Als Limitation adressiert** | Kein neuer Pre-upgrade-Datensatz. Das ist akzeptabel, wenn offen als verbleibende Einschränkung formuliert und nicht als gelöste Validierung verkauft wird. |
| R1.5 – Fixed curves/COP | **Teilweise erfüllt** | Annahmen und eine Vorlauftemperatur-Sensitivität wurden ergänzt. „Cost-optimal“ und Aussagen zu unveränderten Dispatchentscheidungen sind zu stark. |
| R1.6 – Clustering | **Erfüllt** | Die aktuelle Release-CSV zur Clustering-Sensitivität unterstützt die Aussage: 24 konservierende Partitionen, Kostenspanne etwa 11 EUR, kleine Null-SD. Darauf achten, nur die aktuelle Datei und nicht die alte Build-CSV zu zitieren. |
| R1.7 – Hourly deterministic setup | **Als Limitation adressiert** | Keine stochastische/feinere Auflösung ergänzt, aber in den Limitationen diskutiert. Bei vorsichtiger Scope-Formulierung vertretbar. |
| R2.1 – Novelty | **Teilweise bis weitgehend erfüllt** | CP+L-Kontrolle und exakte Decomposition sind ein klarer Beitrag. Die physische Decision-Regret-Neuheit ist in der aktuellen Implementierung schwächer als behauptet. |
| R2.2 – Topology/loss confound | **Fachlich stark erfüllt** | Vier unabhängig optimierte Kontrollen ergeben 95,8/4,7/−0,5 %. Es fehlt die saubere Unterscheidung zwischen Solverziel und nachgelagerter Kostenmetrik. |
| R2.3 – Linearisation rigor | **Teilweise erfüllt** | Solvergrenzen und kurze Fixed-Binary-Vergleiche sind vorhanden. Delay, Modellbeschreibung, Fensterlänge und Geltungsbereich der Aussage bleiben fehlerhaft. |
| R2.4 – Validation/pumping | **Teilweise erfüllt** | Hydraulische Komponenten-/pandapipes-Evidenz wurde ergänzt. Unabhängige Verlustvalidierung fehlt; der interne stündliche Bilanztest scheitert. |
| R2.5 – Generality | **Teilweise bis weitgehend erfüllt** | Balanced 135-case design und Statistik sind vorhanden. Manuskript-Taxonomie und Release sind jedoch nicht synchron, und die Schwellen werden übergeneralisiert. |
| Senior editor – keine Citation lumps | **Erfüllt** | Keine relevante Häufung mehr festgestellt. |
| Senior editor – Abstract ein Absatz | **Erfüllt** | Aktuelle Fassung erfüllt dies. |
| Senior editor – Conclusion ohne Subheadings | **Erfüllt** | Aktuelle Fassung erfüllt dies. |
| Senior editor – Struktur/Format | **Teilweise erfüllt** | Struktur verbessert; finaler sauberer Overleaf-Build und Warnungsprüfung stehen aus. |

## Prüfung des bisherigen Response Letters

`submission_pack/02_correspondence/response_letter.md` ist noch nicht versandfertig. Er ist als Skeleton bezeichnet und enthält mehrere Tatsachenbehauptungen, die die aktuelle Evidenz nicht trägt.

### Zwingend zu korrigierende Aussagen

- Nicht behaupten, dass Scope-Einschränkungen vollständig durch experimentelle Faktoren ersetzt wurden; verteilte Erzeugung wurde nicht als Faktor untersucht.
- Nicht behaupten, der Decision Regret belege physische Undeliverability oder einen tatsächlich ausgeführten Fahrplan.
- 95,9 % auf die korrekte, datenquellenspezifische Rundung 95,8 % ändern.
- Nicht behaupten, Objective-Residualterme hoben sich in allen Differenzen auf.
- Nicht behaupten, der Jahresnetzverlust sei auf 1,2 % validiert.
- „Weeks“ durch zwei 72-h-Fenster ersetzen.
- Nicht „true physics“ oder vollständige nichtlineare Reoptimierung behaupten.
- Nicht sagen, alle Remedy-Forderungen seien übernommen, solange Delay, Bilanz, Recourse und Release offen sind.
- Die alte Fallzahl „81“ vollständig auf das aktuelle 135er Design aktualisieren, wo tatsächlich diese Studie gemeint ist.
- Das 135er Design korrekt als 3×5×3×3 beschreiben; keinen Distributed-Generation-Faktor erfinden.
- Für R1.4 und R1.7 klar zwischen „experimentell gelöst“ und „als Limitation adressiert“ unterscheiden.

### Empfohlene Struktur jeder Antwort

1. Reviewer-Kommentar kurz zitieren/paraphrasieren.
2. Ehrliches Statuswort: implemented, clarified, quantified, or retained as limitation.
3. Konkrete Änderung nennen.
4. Genaue Section-/Table-/Figure- und nach finalem Build Seitenangabe ergänzen.
5. Keine Evidenz behaupten, die nicht in Release/Manuskript reproduzierbar vorhanden ist.

Die Korrespondenz sollte erst nach Abschluss der Ergebnisentscheidungen und nach dem finalen Overleaf-Build aktualisiert werden, damit Seiten-/Zeilenverweise stabil sind.

## Reproduzierbarkeit und Zenodo-/Release-Paket

### P0/P1 – unvollständige synthetische Konfigurationen

`zenodo_paper_1/synth_configs` enthält 84 YAML-Dateien, während Manuskript und Back Matter ein vollständiges 135-Fall-Set suggerieren. Das Changelog nennt weitere Konfigurationen ausdrücklich als späteren Follow-up. Entweder alle 135 Konfigurationen beilegen oder die Reproduzierbarkeitsbehauptung einschränken.

### Lizenz widersprüchlich

Das Manuskript nennt CC BY 4.0 für Code und Daten; `LICENSE`/`CITATION.cff` nennen MIT. Code und Daten dürfen unterschiedlich lizenziert werden, aber dies muss ausdrücklich und konsistent dokumentiert sein. Keine pauschale CC-BY-Aussage, wenn das Release MIT ist.

### Metadaten/Platzhalter

- README enthält noch DOI-Platzhalter `10.5281/zenodo.XXXXXXX`, während die Bibliographie `10.5281/zenodo.21219368` nennt.
- README enthält Platzhalter für Nachname, Betreuung und Partner.
- `CITATION.cff` enthält Platzhalternamen/ORCID, fragliche Affiliationsangaben, Repository-Platzhalter sowie einen alten Titel/eine alte Version.

Alle Metadaten vor Einreichung finalisieren und gegen Manuskript-Autorenliste, Affiliations, DOI und Version prüfen.

### Abbildungen/Tabellen nicht aus dem ausgelieferten Skript reproduzierbar

`tools/figgen_p1_v2.py` enthält noch Beschriftungen für 42 Netzwerke und erzeugt offenbar nur vier Regret-Stufen, während die aktuellen Bilder 135 Fälle und sieben Stufen zeigen. `SOLVED_LINEARISATION_ANALYSIS.md` nennt bei der Fidelity Rule ebenfalls noch 42 Fälle. Die ausgelieferten Skripte erzeugen damit nicht nachweisbar die tatsächlich eingereichten Abbildungen.

**Vorschlag:** Skript, Eingabe-CSV und erzeugte Grafik in einem sauberen Environment neu ausführen; Hash/Datum dokumentieren; alte Artefakte entfernen oder klar als Archiv kennzeichnen.

### Ergebnisverzeichnisse nicht mit der aktuellen Taxonomie synchron

Das Release enthält unter `results/` im Wesentlichen L1/L2/L3/L3plus der alten Taxonomie. `results/L3/meta.json` verweist auf eine alte Konfiguration `Memmingen_L3_MILP.yaml` mit etwa 2,268 Mio. Variablen; das aktuelle Manuskript berichtet für T2P3 etwa 3,154 Mio. T2P6-Konfiguration/-Ergebnisse fehlen. Die aktuelle Modell-Taxonomie ist daher nicht aus dem Release rekonstruierbar.

### Data-availability-Aussage

Die Aussage, alle Skripte produzierten jede Tabelle und Abbildung, ist in der aktuellen Form nicht erfüllt. Bis das Paket synchronisiert ist, die Aussage abschwächen. Idealerweise eine Manifestdatei anlegen:

| Paper-Artefakt | Eingangsdaten | Skript | erwartete Ausgabe | Run-ID/Version |
|---|---|---|---|---|
| Tabelle/Abbildung | konkrete CSV/YAML | konkreter Pfad | PDF/CSV | Commit/DOI |

## Abbildungen und Submission-Dateien

- `F_decomp` passt zu den aktuellen Zahlen 95,8/4,7/−0,5 % und 135 Fällen.
- `F_rule` schneidet Daten oberhalb 75 % ab; Achse korrigieren.
- `F_drift` zeigt Werte bis rund 81 % und widerspricht der manuellen 67,4-%-Korrektur.
- `F_regret` ist ein Balkendiagramm; Caption beschreibt derzeit eine andere Grafik.
- Die PDF-Hashes der Manuskriptabbildungen unterscheiden sich von den Release-Abbildungen. Das ist nicht zwingend falsch, muss aber durch einen reproduzierbaren Erzeugungsweg erklärt sein.
- Eine aktuelle Highlight-Datei liegt nur im alten Build-Verzeichnis. Die alte Version hat fünf Bullets; mindestens zwei überschreiten offenbar Elseviers 85-Zeichen-Empfehlung. „Undeliverable“ ist nicht belegt, und „96 %“ sollte mit der 95,8-%-Quelle abgeglichen werden. Für die finale Einreichung neue Highlights aus der aktuellen Fassung erzeugen.

## Technischer Build-Status

Im lokalen Environment waren keine TeX-Werkzeuge (`latexmk`, `pdflatex`, `bibtex`) verfügbar. Der vorhandene Log-/Aux-Stand ist nicht zuverlässig aktuell: Die Zahl der Labels in der aktuellen Quelle und in der Aux-Datei unterscheidet sich. Deshalb konnte kein belastbarer finaler Compile-Test durchgeführt werden.

Vor Einreichung in Overleaf:

1. „Recompile from scratch“ ausführen.
2. Alle `??`-Referenzen und undefinierten Zitate prüfen.
3. BibTeX-Warnung zum `@software`-Typ beheben.
4. Overfull/Underfull boxes visuell prüfen, insbesondere die frühere 117-pt-Überbreite.
5. Hyperref-Warnungen zu leeren Anchors beseitigen.
6. Jede Tabelle auf Platzhalter, abgeschnittene Einträge und aktuelle Zahlen prüfen.
7. PDF seitenweise gegen Response-Letter-Verweise abgleichen.

## Empfohlene Reihenfolge der Überarbeitung

### Phase 1 – Ergebnisintegrität

1. Energy-Balance-Fehler root-causen und L3 neu exportieren.
2. Entscheiden: echter chronologischer Recourse oder Umbenennung/Abschwächung des Regret.
3. Entscheiden: L6-Delay korrekt implementieren und neu rechnen oder L6-Behauptung entfernen.
4. Vier-Kontroll-Decomposition auf Solverziel vs. Economic Cost bereinigen; bevorzugt objective-aligned neu rechnen.
5. Validierungsclaim auf tatsächliche Nachfrageenergie beschränken oder echte Verlustmessung ergänzen.

### Phase 2 – Manuskriptkonsistenz

1. Taxonomie vollständig neu ordnen.
2. Nichtlinearitäts-/PWL-Beschreibung an Code und 72-h-Experiment anpassen.
3. Stalen Temperaturanhang entfernen oder reproduzierbar erneuern.
4. Zahlen 81,2 %, 19 %, 95,8 % und alle Captions vereinheitlichen.
5. Gleichungen, Einheiten und Referenzen korrigieren.
6. Absolute/universelle Aussagen auf die untersuchte Domäne beschränken.

### Phase 3 – Release

1. 135 Konfigurationen, aktuelle Run-Metadaten und aktuelle Taxonomie bereitstellen.
2. Figuren-/Tabellenskript mit den ausgelieferten Daten reproduzieren.
3. DOI, Autoren, Affiliations, ORCID, Version und Lizenzen bereinigen.
4. Manifest zwischen Paper-Artefakten und Release-Dateien ergänzen.

### Phase 4 – Korrespondenz und Submission

1. Response Letter sachlich neu schreiben und jeden Reviewerpunkt ehrlich einstufen.
2. Erst nach finalem Build genaue Seiten-/Abschnittsverweise einsetzen.
3. Aktuelle Highlights erzeugen.
4. Sauberen Overleaf-Neubuild und PDF-Sichtprüfung durchführen.

## Änderungen, die wahrscheinlich ohne neue Optimierung möglich sind

- Scope- und Terminologiekorrekturen.
- Taxonomie der bereits vorhandenen Läufe.
- 81,2/19/95,8-Zahlenkorrekturen aus aktuellen CSVs.
- Referenz-, Caption-, Einheiten- und Gleichungskorrekturen.
- Entfernen des veralteten Temperaturanhangs.
- Abschwächung/Umbenennung des Regret zu einer monetären Forward-Bewertung.
- Aktualisierung von Metadaten, Lizenztext, Highlights und Response Letter.

## Punkte, die einen neuen Lauf oder mindestens einen neuen Export benötigen

- Aufklärung und Korrektur der stündlichen Energiebilanz.
- Physischer Decision Recourse, falls dieser Claim erhalten bleiben soll.
- Tatsächlich implementierte L6-Transportverzögerung, falls L6 erhalten bleiben soll.
- Objective-aligned Vier-Kontroll-Zerlegung für eine streng vergleichbare 95,8-%-Aussage.
- Echte jährliche Verlustvalidierung, sofern ausreichende Messdaten existieren.
- Reproduzierbare Neugenerierung der aktuellen Figuren und Tabellen aus dem finalen Release.

## Abschließende Empfehlung

Die Arbeit besitzt mit der Vier-Kontroll-Decomposition einen klaren und publizierbaren Kern. Die sicherste Revision besteht darin, diesen Kern stärker in den Mittelpunkt zu stellen und nicht belegte Nebenclaims zu reduzieren. Insbesondere sollten „annual loss validated“, „physically undeliverable“, „true physics“, „one-phenomenon monotone ladder“ und die aktuelle L6-Delay-Aussage nicht in der Einreichung verbleiben, solange die oben beschriebenen Nachweise fehlen.

Nach Behebung der P0-Punkte sollte eine zweite, kürzere Konsistenzrunde erfolgen, anschließend der Response Letter aktualisiert und zuletzt ein sauberer Overleaf-Build geprüft werden.

---

## Audit des Modellcodes und CBC-Smoke-Tests

Stand dieses Modelltests: 20. August 2026. Bei diesem Audit wurden keine Modell-, Konfigurations- oder Datenfiles verändert. Ausgeführt wurden nur Read-only-Prüfungen sowie kleine, temporäre Pyomo/CBC-Smoke-Modelle.

### Kurzurteil

Der Modellcode ist vorhanden, hauptsächlich unter `zenodo_paper_1/calion/`. Eine vollständige Reproduktion der Paper-Läufe ist mit dem ausgelieferten Ordner jedoch nicht möglich: Die reale Memmingen-Eingabedatei fehlt, ein Großteil der YAML-Konfigurationen ist mit dem eigenen Loader nicht lesbar, und die vorhandenen synthetischen Daten passen zeitlich nicht zu den Konfigurationen. Entsprechend wurde kein vollständiger Paper-Run erzwungen.

Darüber hinaus wurden mehrere echte Code-/Formulierungsfehler gefunden. Besonders kritisch für das Paper ist die fehlerhafte PWL-Hydraulik: Inaktive Segmente können Durchfluss aufnehmen und dadurch Druckverlust und Pumpenleistung massiv unterschätzen. Hydrauliksensitive Resultate müssen nach Korrektur neu gerechnet werden.

### P0 – Fehlende Eingabedaten: Paper-Läufe nicht reproduzierbar

Alle sieben Konfigurationen in `zenodo_paper_1/configs/memmingen/` referenzieren `data/Import_Data_Memmingen_epronet.xlsx`. Diese Datei ist nicht enthalten. Vorhanden sind lediglich drei synthetische CSV-Dateien in `zenodo_paper_1/data/synthetic_site/`.

Eine Inventur aller 91 YAML-Dateien ergab:

- 43 Referenzen auf die fehlende `Import_Data_Memmingen_epronet.xlsx`,
- 12 Referenzen auf die ebenfalls fehlende `2025_04_14_Import_Data_Memmingen.xlsx`,
- nur 36 Referenzen auf eine tatsächlich vorhandene synthetische CSV.

Damit fehlen bei 55 von 91 Konfigurationen die Eingabedaten. Ohne diese Dateien können insbesondere die Memmingen-/Paper-Ergebnisse nicht unabhängig neu gerechnet werden.

### P0 – Fehlerhafte PWL-Segmentkopplung der Hydraulik

Fundstelle: `zenodo_paper_1/calion/models/blocks/pipe_pair.py`, Zeilen 948–982 und 1043–1050, insbesondere Zeile 966.

Die Segment-Obergrenze lautet sinngemäß:

```python
pwl_flow[t, s] <= upper_s * pwl_seg[t, s] + M_flow * (1 - pwl_seg[t, s])
```

Für `pwl_seg = 0` wird damit nicht `pwl_flow = 0` erzwungen, sondern ein Durchfluss bis `M_flow` erlaubt. Die Summen für Druckverlust und Pumpenleistung verwenden anschließend auch diese Durchflüsse in inaktiven Segmenten. Der Optimierer kann daher den größten Teil des Flusses durch das Segment mit der kleinsten Steigung schicken, obwohl ein anderes Segment ausgewählt ist.

CBC-Reproduktion für eine einzelne DN200-Leitung, 1.000 m, maximal 69,3978 kg/s, `f = 0,02`, `eta = 0,75`:

| Lastpunkt | PWL-Pumpenleistung / exakte kubische Leistung |
|---:|---:|
| 5 % | 5,76 |
| 20 % | 0,36 |
| 50 % | 0,0576 |
| 90 % | 0,01778 |

Beim 90-%-Fall wählt CBC Segment 1 (`[0, 1, 0]`), verteilt den Durchfluss aber als `[54,13027; 8,327734; 0]` kg/s. 54,13 kg/s laufen somit durch das inaktive Segment 0. Die berechnete Pumpenleistung beträgt 0,000797 MW statt physikalisch etwa 0,044850 MW.

**Korrektur:** Die Obergrenze muss mindestens `pwl_flow[t,s] <= upper_s * pwl_seg[t,s]` lauten. Robuster wäre eine geprüfte disaggregierte PWL-/SOS2-Formulierung. Danach alle L3-/Hydraulik-, Pumpstrom-, Regret- und Decomposition-Ergebnisse neu rechnen.

### P0 – E-Boiler wird gelöst, aber als null exportiert

Fundstellen:

- `zenodo_paper_1/calion/run/result_collector.py`, Zeilen 358–360 und 475–483,
- `zenodo_paper_1/scripts/paper/extract_artefacts.py`, Zeilen 392–394 und 425–440.

Der Result Collector exportiert die asset-spezifische Variable `EBOILER_MAIN_Qth` unter dem Legacy-Key `P2H_Q_th_MW`. Das Artefaktskript sucht dagegen nach `EBOILER_MAIN_Q_th_MW` und erhält deshalb eine Nullserie.

Das erklärt den bereits gefundenen 5-MW-Fehler in `results/L3/dispatch_hourly.csv`: Aus dem Strombezug lässt sich die tatsächliche E-Boiler-Leistung exakt rekonstruieren, obwohl `Q_ek_MW` null ist. Die Optimierungsbilanz selbst ist hier nicht der primäre Fehler; fehlerhaft ist der Export der Paper-Artefakte.

**Korrektur:** Entweder im Artefaktskript `P2H_Q_th_MW`/`P2H_Pel_MW` verwenden oder im Collector konsistente asset-spezifische Alias-Spalten erzeugen. Anschließend Dispatch-, Economics-, Validation-, Tabellen- und Figure-Artefakte neu exportieren.

### P0 – Der als Physikreferenz bezeichnete Forward-Evaluator prüft zentrale Verletzungen nicht

Fundstelle: `zenodo_paper_1/tools/evaluator.py`, Zeilen 278–300 und 305–378.

- `viol["dp_consumer"]` wird initialisiert, aber nie aktualisiert. In Zeilen 375–378 wird lediglich `worst_path` berechnet; ein Verfügbarkeits-/Grenzwerttest fehlt.
- `viol["unmet_demand"]` wird initialisiert, aber im gesamten Evaluator nie aktualisiert.
- Nur `velocity` wird tatsächlich geprüft.
- Der Docstring behauptet für `physics="full"` eine native Transportverzögerung. Im Auswertungspfad ist keine Verzögerungsrechnung implementiert.

Damit sind Nullwerte für Druck- und Nachfrageverletzungen konstruktionsbedingt und kein Nachweis physischer Lieferfähigkeit. Claims wie „physically undeliverable“ oder umgekehrt „feasible under the full evaluator“ sind auf dieser Basis nicht belastbar.

### P0 – Transportverzögerung wird im MILP explizit deaktiviert

Fundstelle: `zenodo_paper_1/calion/models/blocks/pipe_pair.py`, Zeilen 1074–1185, insbesondere Zeile 1117.

Sobald `milp_linearize=True` gilt, wird `Q_consumer` unmittelbar an die ankommende Wärme gekoppelt – unabhängig davon, ob `physics.transport_delay=true` gesetzt ist. Der 24-h-Smoke-Test protokollierte für jede Leitung: `transport delay skipped (milp_linearize mode)`.

Damit ist eine MILP-Stufe mit aktiv modellierter Transportverzögerung im aktuellen Code nicht vorhanden. Der Forward-Evaluator kompensiert dies ebenfalls nicht. L6-/Delay-Aussagen müssen entfallen oder nach echter Implementierung neu gerechnet werden.

### P1 – Investierbare Wärmepumpe und Speicher sind nicht CBC-/MILP-fähig

Fundstellen:

- Wärmepumpe: `zenodo_paper_1/calion/models/blocks/heat_pump.py`, Zeilen 111–117,
- Speicher: `zenodo_paper_1/calion/models/blocks/storage.py`, Zeilen 170–189.

Bei aktivierter Investition sind `cap`, `cap_e` und `cap_p` kontinuierliche Variablen. Die Constraints multiplizieren diese Variablen mit Binärvariablen (`cap * on`, `cap_e * active`, `cap_p * charge_mode`). Dadurch entstehen quadratische/bilineare Constraints.

CBC-Smokes:

- nicht investierbare Wärmepumpe: Polynomgrade `[0, 1]`, optimal gelöst;
- investierbare Wärmepumpe: Grad 2, Abbruch `contains nonlinear terms that cannot be written to LP format`;
- nicht investierbarer Speicher: linear, optimal gelöst;
- investierbarer Speicher: Grad 2, gleicher LP-Writer-Abbruch.

Für eine MILP-Investitionsformulierung sind konstante Big-M-Grenzen und separate Verknüpfungen zur installierten Kapazität nötig. Die festen Paper-Kapazitäten sind hiervon wahrscheinlich nicht direkt betroffen; der allgemeine Investment-Claim des Frameworks aber schon.

### P1 – Mindestlast von CHP, Gas- und Biomassekessel wird ignoriert

Fundstellen:

- Konfiguration beispielsweise `zenodo_paper_1/configs/memmingen/Memmingen_L3_MILP.yaml`, Zeilen 341–361,
- Assembly `zenodo_paper_1/calion/models/component_assembler.py`, Zeilen 392–407,
- Generatorblock `zenodo_paper_1/calion/models/blocks/thermal_gen.py`, Zeilen 14–50.

Die YAMLs definieren `min_load`, etwa 0,3 für CHP und 0,1 für Biomasse/Gaskessel. `_attach_generator_from_unified` liest diesen Parameter nicht. `ThermalGeneratorBlock` besitzt weder eine On/Off-Variable noch eine Mindestlastbedingung. Die konfigurierten Mindestlasten dieser Anlagen haben daher keine Wirkung.

### P1 – CHP-Konfiguration hat eine Gesamtwirkungsgrad-Summe von 120 %

In den Memmingen-Konfigurationen stehen für das CHP `thermal_efficiency = 0,80` und `el_eff = 0,40`. `thermal_gen.py`, Zeilen 35–48, setzt gleichzeitig

```text
Q_th = 0,80 * fuel
P_el = 0,40 * fuel
```

Damit entstehen 1,20 MWh Nutzenergie je MWh Brennstoff. Falls `el_eff` stattdessen als Stromkennzahl oder zusätzlicher Erlösfaktor gemeint war, ist die Implementierung/Semantik falsch benannt. Andernfalls ist die Parametrierung physikalisch unmöglich. Das muss vor Neuberechnung geklärt werden.

### P1 – Eigener YAML-Loader kann ausgelieferte Konfigurationen nicht lesen

Fundstellen:

- `zenodo_paper_1/calion/config/merge.py`, Zeilen 82–94,
- `zenodo_paper_1/calion/utils/simple_yaml.py`, insbesondere Zeilen 56–68, 169–171 und 211–225.

Der Loader verwendet stets den eigenen Teilparser, obwohl PyYAML als Abhängigkeit vorhanden ist. Von 91 YAML-Dateien konnten damit nur 54 geladen werden; 37 schlugen fehl:

- 36 synthetische nodale Konfigurationen verwenden gültige YAML-„indentless sequences“, die `simple_yaml` nicht verarbeiten kann;
- `Memmingen_L3_MILP.yaml` beginnt mit einem UTF-8-BOM, den der Parser nicht entfernt.

Dies ist besonders inkonsistent, weil die Konfigurationen offenbar durch PyYAML erzeugt wurden, die offizielle Laufstrecke sie aber mit einem inkompatiblen Parser einliest.

### P1 – Vorhandene synthetische Daten passen zu keinem ausgelieferten synthetischen Jahreslauf

`Import_Data_yearly.csv` umfasst 8.736 Stunden von 1. Januar 2023, 00:00 Uhr, bis 30. Dezember 2023, 23:00 Uhr. Der komplette 31. Dezember fehlt. Die synthetischen YAMLs fordern dagegen einen Horizont im Jahr 2025. Nach Umgehung des YAML-Parsers endet die Horizontselektion daher mit `Zeithorizont enthält keine Zeitschritte`.

Ein ausgelieferter synthetischer Lauf ist somit ohne manuelle Veränderung von Daten oder Konfiguration ebenfalls nicht reproduzierbar.

### P1 – Forward-Evaluator und Optimierungsmodell verwenden unterschiedliche Rohrgeometrie/Physik

Fundstellen:

- Optimierungsmodell: `pipe_pair.py`, Zeilen 175–180: Innendurchmesser = 0,94 mal Nenndurchmesser;
- Evaluator: `tools/evaluator.py`, Zeile 324: Durchmesser = Nenndurchmesser;
- Evaluator: Zeilen 317–320: Rohrdurchfluss aus zeitlich konstantem Jahresnachfrageanteil;
- Evaluator: Zeilen 330–348: T2P1-Verlustformel und Rücklauftemperaturbehandlung.

Der Durchmesserunterschied ist wegen der starken Durchmesserabhängigkeit des Druckverlusts materiell. Zudem verteilt der Evaluator den stündlichen Gesamtfluss anhand statischer Nachfrageanteile statt anhand stündlicher Knotennachfrage; die untersuchte Lastheterogenität wird im Forward-Flow damit nur eingeschränkt abgebildet. Im T2P1-Self-Consistency-Modus wird die Temperaturdifferenz zum Erdreich durch die Mittelung mit der Erdtemperatur effektiv halbiert, während das Optimierungsmodell eine andere Verlustbeziehung verwendet. Die behauptete Self-Consistency ist deshalb nicht gegeben.

### P1 – Bidirektionale Absolutwert-Linearisierung begrenzt den Durchfluss auf die Hälfte

Fundstelle: `pipe_pair.py`, Zeilen 219–260, besonders 233–245.

Für `m_dot in [-M, M]` verwenden die oberen Absolutwertgrenzen nur `M` statt `2M`. CBC-Smokes mit fixiertem Durchfluss waren bei ±0,25M und ±0,50M lösbar, bei ±0,75M und ±0,90M jedoch infeasible. Die aktuelle Formulierung beschränkt den nutzbaren Betrag somit effektiv auf `M/2`.

Die Paper-Netze scheinen unidirektional zu sein; für den allgemeinen bidirektionalen Modellanspruch ist dies dennoch ein eindeutiger Fehler.

### P1 – Fehlgeschlagene CLI-Läufe melden Exitcode 0

Fundstelle: `zenodo_paper_1/calion/run/__main__.py`, Zeilen 141–160.

Workflow-Ausnahmen werden geloggt und anschließend mit `continue` verworfen; am Ende wird immer `0` zurückgegeben. Reproduktion mit einer nicht existierenden Konfiguration: Fehlermeldung im Log, aber `CLI_EXIT=0`. Batch-Läufe und CI können deshalb fehlgeschlagene Simulationen als erfolgreich behandeln.

### P2 – Weitere Inkonsistenzen

- `P2HBlock.part_load_penalty` wird gespeichert, beeinflusst aber keine Gleichung; die Effizienzserie berücksichtigt diesen Parameter nicht.
- Der alternative Thermal-Network-Exporter sucht nach `TES_Q_charge`/`TES_Q_discharge`, während das Modell `TES_Qc`/`TES_Qd` erzeugt. Dadurch fehlen Speicherflüsse in Teilen dieses Exports.
- Das Rohrmodell verwendet einen festen Reibungsfaktor (standardmäßig 0,02); die konfigurierte Rauheit wird in der MILP-Druckverlustformulierung nicht zur Berechnung eines Reynolds-/Colebrook-abhängigen Reibungsfaktors genutzt. Papertext und Parametertabelle müssen dies eindeutig als Approximation benennen.
- Netzverluste werden in der MILP-Formulierung weitgehend durch temperaturabhängige stationäre Terme auferlegt und verschwinden nicht zwingend bei Nullfluss. Das ist eine Modellannahme mit möglichen Auswirkungen in Niedriglaststunden.

### Teststatus

- Python: 3.12.3
- Pyomo: 6.9.2
- CBC: 2.10.11, lokal verfügbar
- AST-Parse: alle 92 Python-Dateien erfolgreich
- Pytest: 96 von 96 Tests fachlich bestanden; der Prozess endete dennoch mit Exitcode 1, weil die konfigurierte Coverage nur 16,23 % statt mindestens 60 % betrug.
- Besonders geringe Testabdeckung: `pipe_pair.py` ca. 3 %, `thermal_node.py` ca. 3 %, `network_manager.py` ca. 5 %, `storage.py` ca. 7 %. Die grünen Unit-Tests validieren die eigentliche Optimierungsphysik daher kaum.
- Ein 24-h-Netz-Smoke mit vorhandenen synthetischen Daten konnte nur nach bewusster Umgehung des offiziellen YAML-Loaders und manueller Anpassung des Horizonts auf 2023 ausgeführt werden. CBC löste dieses modifizierte Fixed-Capacity-MILP optimal (2.670 Variablen, 410 Binärvariablen, 3.247 Constraints, Zielfunktion 42.231,12 EUR). Dies beweist lediglich, dass der Grundpfad unter diesen manuellen Eingriffen läuft; es reproduziert keinen Paper-Fall.

### Konsequenz für die Einreichung

Vor einer Einreichung sollten mindestens folgende Schritte erfolgen:

1. Fehlende Memmingen-Daten bereitstellen oder Data-Availability-/Reproducibility-Claim klar einschränken.
2. PWL-Segmentkopplung korrigieren und alle hydrauliksensitiven Ergebnisse neu rechnen.
3. E-Boiler-Key-Mapping korrigieren und alle Paper-Artefakte neu exportieren.
4. Forward-Evaluator um echte Nachfrage-, Druck- und Delay-Prüfungen ergänzen oder entsprechende Claims entfernen.
5. Mindestlast- und CHP-Wirkungsgradsemantik korrigieren und deren Ergebniswirkung prüfen.
6. YAML-/Daten-/Horizont-Paket in einem frischen Environment end-to-end testen.
7. Erst danach Paper, Response Letter und Korrespondenz an die neu erzeugten Resultate anpassen.

**Gesamtbewertung des Codes:** In der vorliegenden Form ist das Release weder end-to-end reproduzierbar noch ausreichend validiert. Der PWL-Hydraulikfehler und die defekten Forward-Evaluator-Diagnosen berühren zentrale Paper-Aussagen und erfordern vor einer belastbaren Einreichung eine Korrektur mit Neuberechnung.
