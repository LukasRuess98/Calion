# Chat-Review: Paper, Reviewer-Anforderungen und Modellcode

Stand: 27. August 2026

## 1. Kurzurteil

**Empfehlung: Major Revision vor der Wiedereinreichung.**

Das Manuskript hat eine klare und praktisch relevante Kernbotschaft: In dem untersuchten zentral versorgten, radialen Fernwärmesystem dominiert die Sichtbarkeit thermischer Verluste den zusätzlichen Nutzen räumlicher Netzdetails. Mehrere der von FHG eingebrachten Korrekturen sind fachlich richtig und verbessern das Paper. In der derzeitigen Overleaf-Fassung bestehen jedoch noch einige submission-kritische Probleme:

1. Das Overleaf-Paket ist nicht vollständig baubar, weil alle neun referenzierten Ergebnisabbildungen fehlen.
2. Die behauptete saubere gekreuzte 2×2-Zerlegung ist in den tatsächlich gerechneten Fällen durch weitere Parameterunterschiede konfundiert.
3. Der Begriff „decision regret“ und mehrere Aussagen über Änderungen der Dispatch-Entscheidung sind methodisch stärker als die tatsächlich durchgeführte Forward-Evaluation.
4. Validierung, Kalibrierung und reine Code-/Bilanzverifikation werden noch nicht sauber getrennt.
5. Der im Paper beschriebene High-Fidelity-Evaluator ist deutlich umfassender als `tools/evaluator.py` tatsächlich implementiert.
6. Das öffentlich verlinkte Zenodo-Artefakt entspricht weder der aktuellen Paper-Version noch dem behaupteten 135-Fälle-Reproduktionspaket.
7. Die Antwort an die Reviewer ist noch nicht vollständig wahrheits- und versionssynchron; mehrere zugesagte Änderungen sind im Manuskript nicht oder nur teilweise umgesetzt.

**In der aktuellen Form würde ich das Paper noch nicht einreichen.** Nach Behebung der P0-Punkte unten ist die Arbeit grundsätzlich gut verteidigbar, wenn die Aussagen enger an die tatsächlich ausgeführten Modelle und Tests gebunden werden.

## 2. Prüfgrundlage und Versionsentscheidung

Als maßgebliche Manuskriptfassung wurde ausschließlich verwendet:

- `docs/paper_1/submission_pack/overleaf/`

Als Reviewer-Korrespondenz wurden verwendet:

- `docs/paper_1/submission_pack/02_correspondence/Reviewer_Mail.txt`
- `docs/paper_1/submission_pack/02_correspondence/response_letter_tightened.md`
- `docs/paper_1/submission_pack/02_correspondence/response_letter.md` nur zur Erkennung veralteter Inhalte

`draft` und `latex_build` wurden nur als alte Vergleichs-/Auditquellen behandelt. Sie dürfen nicht als Quelle für den aktuellen Submission-Stand dienen.

Der Modellcode, die Paper-Skripte, Tests, Konfigurationen und das lokale Zenodo-Paket wurden ebenfalls geprüft. Außer dieser Datei wurden keine Dateien absichtlich verändert.

## 3. P0 – Blocker vor der Einreichung

### P0.1 Das aktuelle Overleaf-Paket ist nicht selbständig baubar

`overleaf/main.tex` referenziert neun Abbildungen, die weder im Overleaf-Ordner noch an anderer Stelle im Repository vorhanden sind:

- `memmingen_network`
- `F_demand`
- `mixing_valve_offset`
- `F_decomp`
- `F_regret`
- `F_rule`
- `F_drift`
- `F_tsup`
- `F_solvetime`

Auch `overleaf/README.txt` nennt `memmingen_network.png`, die Datei fehlt aber. Eine aktuelle `main.pdf` liegt ebenfalls nicht bei. Alte `.fls`-Informationen zeigen, dass die Bilder früher lokal vorhanden waren; sie sind nur nicht Teil des aktuellen Pakets.

**Erforderliche Änderung:** Alle finalen Abbildungen in den Overleaf-Ordner aufnehmen, Dateinamen und Groß-/Kleinschreibung prüfen und anschließend einen vollständigen Clean Build aus ausschließlich diesem Ordner ausführen. Zusätzlich `highlights.txt` und – falls von der Zeitschrift benötigt – die finale Graphical-Abstract-Datei in das maßgebliche Submission-Paket aufnehmen.

### P0.2 Die „clean crossed 2×2 decomposition“ ist nicht sauber identifiziert

Fundstellen:

- `overleaf/main.tex`, etwa Zeilen 267–292 und 681–704
- `overleaf/base_formulation_v2.tex`, etwa Zeilen 27–30 und 136–148
- `overleaf/computational_setup_v2.tex`, etwa Zeilen 13–18
- `overleaf/appendices_cited_v2.tex`, etwa Zeilen 71–73
- `overleaf/tab_decomposition.tex`

Die Methoden behaupten, dass sich die vier Zellen ausschließlich in Verlustsichtbarkeit und räumlicher Topologie unterscheiden. Die Ergebnisdiskussion räumt jedoch ein, dass ND0 und CP zusätzlich andere Rücklauftemperaturen, Heizkurven bzw. Wärmepumpen-COPs verwenden. Damit ist die ursprüngliche Differenz nicht kausal nur „Topology“ zuzuordnen.

Der physics-matched Kontrolllauf ND0* zeigt ungefähr:

| Anteil | Effekt |
|---|---:|
| Verlustsichtbarkeit | EUR 19,737 bzw. 95.8 % |
| echte Topologiekomponente | EUR 52 bzw. 0.25 % |
| Parameter-/Konfigurationseffekt | EUR 909 bzw. 4.4 % |
| Interaktion | EUR −107 bzw. −0.5 % |
| Gesamtdifferenz | EUR 20,591 |

Die fünf Beträge schließen arithmetisch, aber die im Methodenteil angekündigte dreiteilige, saubere faktorielle Zerlegung nicht.

**Bevorzugte Lösung:** Alle vier 2×2-Zellen mit identischen nicht-faktoriellen Physikparametern erneut rechnen. Nur Verlustsichtbarkeit und Topologie dürfen wechseln.

**Falls keine Neuberechnung erfolgt:** Die ursprüngliche Zerlegung ausdrücklich als konfigurativ konfundiert kennzeichnen, ND0* bereits im Design-/Methodenteil einführen und die Auswertung als Sensitivitätsanalyse statt als sauber kausal identifiziertes 2×2-Experiment darstellen. Die EUR-909-Komponente darf nicht erst nachträglich als Nebeneffekt erscheinen.

### P0.3 „Decision regret“ ist kein mathematisches Regret gegen ein High-Fidelity-Optimum

Fundstellen:

- `overleaf/main.tex`, etwa Zeilen 94–123, 369–400, 714–748
- `overleaf/tab_regret.tex`
- `overleaf/conclusions_v2.tex`
- `02_correspondence/response_letter_tightened.md`, etwa Zeilen 9 und 45

Gemessen wird ein vorzeichenbehafteter Kostenunterschied einer fixierten Schedule unter einer Forward-Evaluation. Es gibt kein unter derselben hohen Fidelity optimiertes Referenzoptimum. Der Wert kann negativ sein. Das Manuskript erklärt diese Einschränkung zwar lokal, verwendet „decision regret“ aber weiterhin als zentralen Begriff. Gleichzeitig verspricht die Antwort an die Reviewer, den Begriff nicht mehr zu verwenden.

**Erforderliche Änderung:** Im gesamten Manuskript, in Keywords, Tabellen, Bildtexten und Korrespondenz konsistent in beispielsweise

- „forward-evaluated schedule-cost difference“ oder
- „forward-evaluated cost gap“

umbenennen. Wenn „regret“ unbedingt bleiben soll, muss es unmissverständlich als studiespezifische, signierte Proxy-Größe definiert und von formalem Optimierungs-Regret abgegrenzt werden. Die erste Variante ist reviewer-sicherer.

### P0.4 L4/L5 wurden nicht reoptimiert; Aussagen über Dispatch-Entscheidungen sind daher unzulässig

Fundstellen:

- `overleaf/main.tex`, etwa Zeilen 484–497 und 800–802
- `overleaf/fidelity_vs_cost_v2.tex`, etwa Zeilen 29–31
- `overleaf/conclusions_v2.tex`, etwa Zeilen 38–40
- `overleaf/tab_criteria.tex`

L4 und L5 sind Fixed-Schedule-Forward-Evaluations. Dass sich der Dispatch dort nicht ändert, ist konstruktionsbedingt: Die Schedule wurde fixiert. Daraus folgt nicht, dass eine L4-/L5-Optimierung dieselbe Dispatch-Entscheidung ergäbe oder keinen ökonomischen Mehrwert hätte.

**Erforderliche Änderung:** Aussagen wie „does not change dispatch decisions“, „no material decision gain“ oder gleichwertige Formulierungen ersetzen durch:

> The fixed L1 schedule remained feasible and inexpensive under the L4/L5 valuation overlay; the optimal L4/L5 dispatch was not computed.

Die vorsichtige Formulierung in `main.tex` um Zeilen 484–497 sollte als Standardformulierung im gesamten Paper verwendet werden.

### P0.5 Validierung, Kalibrierung und Verifikation sind vermischt

Fundstellen:

- `overleaf/validation_protocol_v2.tex`, etwa Zeilen 24–32
- `overleaf/validation_results_v2.tex`, insbesondere etwa Zeilen 55–60
- `overleaf/tab_val_targets.tex`
- `overleaf/tab_validation.tex`, insbesondere etwa Zeilen 53–54
- `overleaf/main.tex`, Validierungs- und Limitationsabschnitte
- `02_correspondence/response_letter_tightened.md`, etwa Zeile 162

Widersprüche und Überdehnungen:

- Das Protokoll sagt, mehrere Gates seien nicht erfüllt und Temperatur-Gates mangels Instrumentierung nicht möglich; Tabellen vermitteln dagegen, alle vier Gates seien erfüllt.
- Die Antwort an die Reviewer sagt, es gebe keinen belastbaren held-out physischen Knoten; das Manuskript spricht von sechs held-out Validierungsknoten.
- Jährlich gelieferte Wärme ist ein exogener Abrechnungs-/Demand-Input. Dessen Reproduktion ist keine unabhängige Validierung von Netzverlusten.
- Interne Energiebilanzschließung ist Code-/Modellverifikation, keine empirische Validierung.
- Eine fest vorgegebene oder kalibrierte Quellrücklauftemperatur ist kein unabhängiger Validierungswert.
- Ohne Quellenergiemessung kann der Verlust nicht unabhängig aus Lieferenergie allein validiert werden.
- Der pandapipes-Vergleich prüft die Druckverlustrechnung des Trunks bzw. Cross-Solver-Konsistenz, aber nicht stationäre/laterale Verluste, Pumpenenergie oder die empirische Gültigkeit des Gesamtsystems.
- Die installierte Pumpen-Nennleistung von 110.8 kW validiert keinen modellierten Peak von ungefähr 3 kW und erst recht nicht den Jahresenergieverbrauch.

**Erforderliche Änderung:** Drei explizite Kategorien verwenden:

1. **Calibration / input grounding:** Welche Inputs stammen aus Messung, Abrechnung oder Kalibrierung?
2. **Code/model verification:** Bilanzschließung, Solver- und pandapipes-Cross-Checks.
3. **Empirical validation:** Ausschließlich wirklich unabhängige, nicht zur Kalibrierung verwendete Beobachtungen.

Die Verlusthöhe muss ohne unabhängige quellseitige Energiemessung als modellbasierte, sensitivitätsgeprüfte Größe bezeichnet werden. Reviewer-Punkt R2.4 ist derzeit nur teilweise erfüllt.

### P0.6 Der beschriebene Evaluator entspricht nicht `tools/evaluator.py`

Manuskript-Fundstellen:

- `overleaf/main.tex`, etwa Zeilen 373–433

Code-Fundstellen:

- `tools/evaluator.py`, insbesondere etwa Zeilen 161–179, 243–251, 292–350, 392–428 und 450–467
- `tools/regret_decomp.py`, insbesondere etwa Zeilen 59–60 und 111–135

Der Text sagt sinngemäß, Generation, Commitment, Speicher, Netzbezug und weitere Entscheidungen würden übertragen, physikalische Zustände und Speicher-SOC neu berechnet sowie Bounds und zyklische Bedingungen geprüft. Der Code liest im Wesentlichen Nachfrage, Vorlauf- und Rücklauftemperatur. Er enthält keine vollständige Übergabe oder Rekonstruktion von Erzeuger-Commitment, Speicher-SOC, Speicherleistung oder Netzbezug.

Konkrete Abweichungen:

- Keine implementierte Transportverzögerung im Evaluator; „delay“ erscheint nur beschreibend, nicht als Zeitverschiebung/Lag.
- Auf dem Rückweg wird dieselbe globale Rücklauftemperatur für alle Rohre verwendet; es gibt keine vollständige rückwärtige Temperaturkaskade mit Mischung.
- Leitungsströme werden proportional aus gelieferter Nachfrage aufgeteilt, nicht aus dem tatsächlich optimierten Fahrplan inklusive Verlustdeckung oder Zirkulation rekonstruiert.
- Die Auswertung lädt aggregierte Kosten und addiert skalare Wärme-/Pumpenkostendifferenzen. Das ist keine ausführbare Recourse-Optimierung.
- Zusätzliche Verlustwärme wird mit `gas_price / 0.9` bewertet, ohne stündliche Einheitenverfügbarkeit, Kapazität, Rampen, CHP-Kopplung oder zusätzliche Emissionen nachzubilden.
- Pumpenstrom wird mit einem mittleren Strompreis bewertet; Grid-Balance und inkrementelle Nachfrageentgelte werden nicht aktualisiert.
- Angenommene Jahresverluste werden gleichmäßig auf Zeitschritte verteilt. Dadurch kann eine stündlich verlustbewusste Schedule künstlich als unterdeckend erscheinen.
- Die Policies „base/peak/emergency“ in `regret_decomp.py` verwenden feste Kostensätze 72.2/90/1000; „peak“ ist nicht die tatsächlich teuerste stündlich verfügbare Einheit, wie das Manuskript nahelegt.
- Geprüfte Verletzungen betreffen im Wesentlichen Geschwindigkeit, Verbraucherdruck und Unterdeckung, nicht alle im Text genannten Temperatur-, Speicher-, Einheiten- und Stromrestriktionen.
- Der Fanning-/Darcy-Reibungsansatz verwendet eine dynamische Viskosität von `1e-3 Pa s`, also ungefähr Wasser bei Raumtemperatur; für das betrachtete Temperaturniveau sollte eine passende temperaturabhängige Größe oder eine begründete Sensitivität verwendet werden.

**Erforderliche Änderung:** Entweder den Evaluator substanziell erweitern und mit automatisierten Tests belegen oder das Paper konsequent als **valuation overlay / screening evaluator** beschreiben. Begriffe wie „true cost“, „full execution simulation“, „post-recourse feasibility“ und „physically deliverable“ sind mit dem aktuellen Code zu stark.

### P0.7 Das öffentlich verlinkte Zenodo-Artefakt ist nicht die behauptete Revision

Fundstellen:

- `overleaf/back_matter_v2.tex`, etwa Zeilen 35–44
- lokaler Ordner `zenodo_paper_1/`
- öffentlich verlinkter Zenodo-Record: <https://zenodo.org/records/21219368>

Der Record ist öffentlich als Version v1.0.0 mit Veröffentlichung vom 6. Juli 2026 beschrieben. Die Metadaten nennen 36 synthetische Konfigurationen und einen älteren Paper-Titel bzw. eine ältere Hierarchie. Das ist nicht das im aktuellen Manuskript behauptete v1.3-/135-Zellen-Reproduktionspaket.

Auch lokal fehlen wichtige Artefakte:

- die aktuellen Memmingen-Control-Konfigurationen wie T0P0, T0P1a/b, T2P0 und T2P1_defU,
- die zugehörigen Ergebnis-CSVs,
- ein vollständiger `results/`-/`data/`-Stand für die Paper-Tests,
- ein sauber reproduzierbarer aktueller Figures-/Tables-Export.

**Erforderliche Änderung:** Vor Submission eine neue, tatsächlich vollständige Zenodo-Version veröffentlichen und erst danach DOI, Version, Titel und Umfang im Manuskript aktualisieren. Alle README-Kommandos aus einer sauberen Umgebung testen. Der Text darf bis dahin nicht behaupten, das aktuelle Revisionspaket sei bereits unter diesem Record verfügbar.

### P0.8 Die finale Reviewer-Antwort ist noch nicht einreichbar

`response_letter.md` ist ein veraltetes Gerüst und darf nicht verwendet werden. `response_letter_tightened.md` ist die bessere Grundlage, enthält aber noch:

- falsche oder veraltete Abbildungs-/Tabellen-/Abschnittsverweise,
- nicht vollständig erfüllte Zusagen,
- eine unfertige Abschlusscheckliste,
- teilweise verkürzte statt wörtlich übernommene Reviewer-Kommentare,
- die Behauptung von fünf Hauptabschnitten, obwohl das Manuskript vier hat,
- die Behauptung, Highlights und Graphical Abstract seien bereits erneut eingereicht, obwohl sie im aktuellen Paket fehlen.

Die Korrespondenz muss nach allen Manuskriptkorrekturen noch einmal vollständig neu synchronisiert werden.

## 4. Weitere Manuskriptbefunde

### 4.1 Die Fidelity-Stufen sind keine monotone „one-phenomenon ladder“

Fundstellen:

- `overleaf/main.tex`, etwa Zeilen 281–316
- `overleaf/tab_design_grid.tex`
- `overleaf/tab_contrasts.tex`
- `overleaf/extended_physics_v2.tex`

L2 und L4/L5 sind teilweise Forward-Evaluations statt Optimierungsstufen. L6 ist L3 plus Verzögerung und erbt L4/L5 nicht. L1→L2 fügt Temperatur-Forward-Evaluation hinzu; L2→L3 entfernt zugleich Evaluationslogik und fügt Druckphysik hinzu; L3→L4 wechselt wieder den Modus und fügt mehrere Mechanismen gleichzeitig hinzu.

**Vorschlag:** Nicht als monotone Leiter darstellen. Besser: „targeted ablations and forward-evaluation overlays relative to a common operational baseline“. Jede Stufe mit den Spalten „optimised vs evaluated“, „inherited mechanisms“ und „new mechanisms“ kennzeichnen.

### 4.2 Dimensionsfehler in der Wärmestromgleichung

`overleaf/main.tex`, etwa Zeilen 821–823, schreibt sinngemäß:

`Q = m_dot (T_supply - T_return)`

Es fehlt die Wärmekapazität und bei MW-Einheiten die Umrechnung:

`Q_MW = m_dot_kg/s * c_p,kJ/(kg K) * DeltaT_K / 1000`.

Der FHG-Faktor `10^6` in der Loss-Number-/Jahresenergie-Gleichung ist dagegen dimensionsrichtig und sollte beibehalten werden.

### 4.3 Supplement-Nummerierung ist systematisch um eins verschoben

`overleaf/supplementary.tex` bindet zuerst `tab_contrasts` ein. Damit ist dies Tabelle S1; alle nachfolgenden Tabellen verschieben sich um eins. Die aktuell hart kodierten Verweise sind falsch:

- `cost_accounting_v2.tex`, etwa Zeile 23: S1 muss S2 sein.
- `main.tex`, etwa Zeile 872: S2 muss S3 sein.
- `main.tex`, etwa Zeile 957: S5 muss S6 sein.
- `main.tex`, etwa Zeile 1013: S4 muss S5 sein.
- `main.tex`, etwa Zeile 1018: S3 muss S4 sein.

**Vorschlag:** Keine hart kodierten Supplement-Nummern. Alle Tabellen mit Labels versehen und ausschließlich per `\ref` referenzieren.

### 4.4 Supplement-Titel ist veraltet

`overleaf/supplementary.tex`, etwa Zeilen 31–33, verwendet noch „Estimation Bias versus Decision Regret ...“ statt des aktuellen Haupttitels „Loss Visibility versus Spatial Detail in District-Heating Dispatch Optimisation“.

### 4.5 Weitere Cross-Reference-Probleme

- `main.tex`, etwa Zeile 591, verweist für Limitationen auf Section 4/Conclusions; die eigentliche Limitationsdiskussion steht in §3.14.
- `main.tex`, etwa Zeile 729, erzeugt voraussichtlich ein fehlerhaftes „S3.9“ durch die Kombination aus hartem `S` und `\ref`.
- Alle Seiten-/Zeilen-/Tabellenangaben in der Response Letter erst nach dem finalen Clean Build festschreiben.

### 4.6 Tabellenfehler in `tab_val_targets.tex`

In etwa Zeilen 37–38 besitzen Zeilen nur drei Zellen, obwohl vier Spalten definiert sind; vermutlich fehlt jeweils der Status. Zudem werden beobachtete Werte in der Spalte „Gate“ eingetragen, wodurch Ziel, Beobachtung und Pass/Fail semantisch vermischt werden.

**Vorschlag:** Spalten strikt als `Quantity | Ex-ante gate | Observed value | Status` führen und für nicht prüfbare Gates `not testable with available instrumentation` statt `pass` verwenden.

### 4.7 Solver-Toleranz ist inkonsistent

Methoden/Synthese nennen 0.01 %, die Ergebnisse für synthetische Fälle teilweise ≤0.1 %. Eine einheitliche Toleranz nennen oder transparent zwischen Ziel, akzeptierter Restlücke und tatsächlich beobachteter Lücke unterscheiden.

### 4.8 Nichtlineare Referenzläufe vorsichtiger und vollständiger berichten

Die 72-h-Winter-/Herbst-Fixed-Binary-Läufe ergeben ungefähr −0.15 % bzw. −0.33 % mit Gaps von 0.009 bzw. 0.025. Der Ganzjahreslauf liefert keinen Incumbent; der Sommerfall bleibt infeasible bzw. ungeklärt. Das Manuskript ist überwiegend vorsichtig, die Response Letter aber nicht.

Korrekturen:

- 72 h sind drei Tage, nicht „a week“.
- QCP und „nonlinear exponential NLP“ nicht synonym verwenden; exakt die gelöste Modellklasse nennen.
- Wenn behauptet wird, jeder Effekt werde gegen Incumbent und Bound berichtet, müssen diese Werte und das daraus abgeleitete Effektintervall tatsächlich in der Tabelle stehen.
- Keine Aussage über globale Optimalität ohne entsprechende Zertifizierung.
- Sommer-Infeasibility als ungeklärte numerische/modellbedingte Einschränkung behandeln, nicht als physikalischen Befund.

### 4.9 Generalisierung und synthetisches Design enger formulieren

- Die 135 Zellen sind ein modellrauminterner Faktoriell-/Robustheitstest, keine externe Validität im empirischen Sinn.
- Die Sizing Convention wird erwähnt, aber nicht präzise genug spezifiziert oder quantifiziert.
- Behauptete Regressions-Konfidenzintervalle fehlen; vorhanden ist primär ANOVA-Auswertung.
- „survives every perturbation“ ist zu absolut; auf die tatsächlich getesteten Faktoren und Bereiche beschränken.
- Mechanismen in `physics_null_mechanisms` sind plausible Hypothesen, keine nachgewiesenen Kausalmechanismen.
- „specified before observing the outcome“ klingt wie eine Präregistrierung. Falls keine dokumentierte Präregistrierung existiert, nur „held-out from fitting/calibration“ schreiben.
- Die Loss Number lässt sich nicht allein aus Rohrinventar bestimmen; sie benötigt mindestens Temperaturen und Jahresnachfrage. „parameter-free“ höchstens als „no fitted free parameter beyond listed physical inputs“ formulieren.
- Die vorgeschlagenen Bänder sind heuristische, judgment-basierte Screening-Bänder und keine Garantie.

### 4.10 Objective-/Cost-Accounting-Text intern synchronisieren

Die FHG-Ergänzung des Storage-Cycling-Terms stimmt mit `calion/models/component_assembler.py` etwa Zeilen 1040–1058 überein. Auch die Storage-Loss-Konvention entspricht `calion/models/components/storage.py` etwa Zeilen 140–143.

Problematisch ist dagegen `overleaf/tab_objdecomp.tex`, etwa Zeilen 4–7: Der Residualterm wird als nahezu konstant und als sich in jeder Bias-/Gap-Differenz aufhebend beschrieben. Die berichteten Residualwerte unterscheiden sich jedoch um ungefähr EUR 5,900. `cost_accounting_v2.tex` sagt selbst, die Aufhebung werde nicht vorausgesetzt.

**Vorschlag:** Tabellenkommentar korrigieren und für jede relevante Differenz explizit zeigen, welche Kostenbestandteile wechseln.

### 4.11 Rundung und Terminologie

- `tab_robustness`/`tab_gap_stability` nennen 95.9 %, der Haupttext 95.8 %. Eine Quelle und Rundungsregel verwenden.
- „operator-accounting cost“ und „economic operating cost“ vereinheitlichen.
- Der behauptete „standard CHP self-use carbon credit“ braucht eine präzise Formel und Quelle oder muss als studiespezifische Accounting-Konvention bezeichnet werden.
- Breite Aussagen wie „spatial routing is immaterial“ immer auf zentral versorgte, radiale Systeme, gegebene Kapazitäten und die verwendete Kostenrechnung begrenzen.

### 4.12 Manuskriptbereinigung

In `main.tex` stehen zahlreiche interne Kommentare, Marker und TODOs, unter anderem ungefähr in Zeilen 154, 371 und 716. Vor Submission alle FHG-/Author-Polish-/DRAFTED-/TODO-Kommentare und nicht benötigte Scaffold-Texte entfernen.

Der BibTeX-Log warnt, dass der Typ `@software` für `ruess_2026_calion` im Elsevier-Stil unbekannt ist. Einen vom Stil unterstützten Typ, z. B. `@misc`, verwenden und die finale Ausgabe kontrollieren.

Positiv: Der Abstract besteht aus einem Absatz, die Conclusions haben keine Unterüberschriften, und das Manuskript ist inzwischen in vier Hauptabschnitte strukturiert. Diese Editoranforderungen sind formal erfüllt.

## 5. Reviewer-Compliance-Matrix

| Punkt | Status | Review |
|---|---|---|
| R1.1 Scope/operation planning statt Netzdesign | Erfüllt | Scope ist deutlich enger und korrekt positioniert. |
| R1.2 Accuracy vs sensitivity | Teilweise | Sensitivitätsidee verbessert, aber „regret“ und einige starke Entscheidungsbehauptungen bleiben. |
| R1.3 Delay separation | Weitgehend | Delay ist separater, aber die behauptete one-phenomenon ladder stimmt nicht. |
| R1.4 Validation after upgrades | Teilweise | Mehr Checks vorhanden, aber Validierung/Kalibrierung/Verifikation und Messprovenienz bleiben widersprüchlich. |
| R1.5 Restrictive assumptions | Erfüllt mit kleiner Korrektur | Temperatur-Sweep vorhanden; als diskrete Forward-Evaluation und „lowest feasible tested point“ beschreiben. |
| R1.6 Clustering | Erfüllt mit Textkorrektur | Robustheitstest vorhanden; Response-Letter-Behauptung, Baseline folge Billing Boundaries, ist im Paper nicht belegt. |
| R1.7 Deterministic hourly/no reserves | Erfüllt | Einschränkung ist transparent. |
| R2.1 Novelty | Teilweise | Beitrag klarer, aber Regret-/Decision-/Loss-Number-Claims noch zu stark. |
| R2.2 Clean 2×2 attribution | Kritisch teilweise | CP+L und Controls helfen, aber der zusätzliche Physik-/Konfigurationsunterschied verhindert derzeit eine saubere kausale Zerlegung. |
| R2.3 Nonlinear references and certificates | Teilweise | Läufe ergänzt; Incumbents/Bounds/Effektintervalle fehlen in der behaupteten Vollständigkeit; 72 h wird fälschlich als Woche bezeichnet. |
| R2.4 Grounding/validation | Kritisch teilweise | Kein unabhängiger Loss-/Pumpenenergie-Nachweis; L4/L5 nicht reoptimiert; held-out-Aussagen widersprechen sich. |
| R2.5 Synthetic generalisation | Teilweise | 135-Zellen-Design stark verbessert; Sizing Convention, CIs, Gap-Toleranz und Artefaktfreigabe unvollständig. |
| Senior editor: one-paragraph abstract | Erfüllt | Ein Absatz. |
| Senior editor: conclusions without subheadings | Erfüllt | Keine Unterüberschriften. |
| Senior editor: five-to-four section compression | Erfüllt | Vier Hauptabschnitte; Response Letter muss dies korrekt nennen. |
| Senior editor: references/citation bundles | Weitgehend | Bündel wurden reduziert; ein behaupteter automatischer Citation-Lumping-Check ist im Paket nicht erkennbar. |
| Highlights/graphical abstract | Nicht nachweisbar | Im maßgeblichen Overleaf-Paket fehlen die finalen Dateien. |

**Gesamtbewertung zur Reviewer-Erfüllung:** Die meisten Punkte wurden substanziell adressiert, aber R2.2, R2.3, R2.4 und R2.5 sind noch nicht vollständig erfüllt. Die Response Letter darf daher nicht behaupten, sämtliche Forderungen seien vollständig erledigt.

## 6. Exakte Code–Paper-Ungereimtheiten

### 6.1 Netzwerkfehler können still in ein Copperplate-Modell zurückfallen

Fundstellen:

- `calion/models/model_finalizer.py`, etwa Zeilen 219–262 und 582–628

Bei deaktivierter Netzkonfiguration, fehlenden Knoten oder beliebigen Exceptions wird `_network_enabled=False` gesetzt und mit einer globalen Wärmebilanz weitergebaut. Ein fehlerhaftes Rohr ließ sich im Smoke-Test reproduzieren: Das Modell wurde trotzdem erzeugt, Netzphysik und Netzverlust verschwanden, die globale `ht_balance` blieb aktiv.

**Risiko für das Paper:** Ein angeblicher Netzfall kann bei Konfigurations- oder Datenfehlern unbemerkt als Copperplate-Fall gerechnet werden.

**Erforderliche Codeänderung:** Für wissenschaftliche Runs `strict_network=True` oder gleichwertig: bei erwarteter Netzphysik fail fast. Nach Modellbau per Assertion prüfen:

- `_network_enabled is True`,
- erwartete Anzahl Knoten/Rohre,
- erwartete Verlust-, Druck- und Delay-Komponenten,
- Hash der tatsächlich geladenen Konfiguration.

### 6.2 Die öffentliche `calion.Network`-API schreibt falsche Storage-Schlüssel

Fundstellen:

- `calion/network.py`, etwa Zeilen 164–173
- `calion/models/component_assembler.py`, etwa Zeilen 974–1003 und 1301–1344

Die API schreibt unter anderem `energy_mwh`, `power_mw`, `eta_charge`, `eta_discharge`, `soc_init_mwh`, `self_discharge_rate`. Der Assembler erwartet `max_energy_mwh`, `max_power_mw`, `eff_charge`, `eff_discharge`, `soc0_mwh`, `loss_hour`.

Reproduzierter Smoke-Test:

| Angefordert | Tatsächlich im Modell |
|---|---:|
| 12 MWh Kapazität | 50,000 MWh |
| 3 MW Leistung | 50 MW |
| eta charge/discharge 0.81/0.82 | 0.95/0.95 |
| SOC initial 4 MWh | 0 MWh |
| stündlicher Verlust 0.02 | Retention 0.9999 |

Das ist ein schwerer API-Korrektheitsfehler. Die Paper-YAMLs können einen anderen Pfad verwenden, aber API-basierte Reproduktions- und Smoke-Tests sind derzeit nicht vertrauenswürdig.

### 6.3 Physik-Flags der `Network`-API werden ignoriert

Fundstellen:

- `calion/network.py`, etwa Zeilen 490–503
- `calion/models/network/network_manager.py`, etwa Zeilen 88–102

Die API schreibt `heat_loss_enabled`, `pressure_drop_enabled`, `transport_delay_enabled`; der Network Manager liest eine andere Struktur unter `thermal_network.physics` und nimmt für Druck standardmäßig `True` an.

Reproduzierter A/B-Test: Wärmeverlust `true` und `false` sowie Druck `false` lieferten beide denselben Verlust von 0.0375 MWh und jeweils drei Pumpenvariablen. Die gesetzten Flags wirkten also nicht.

**Erforderliche Codeänderung:** Ein kanonisches Config-Schema mit Validierung verwenden; unbekannte oder ignorierte Keys müssen einen Fehler auslösen. Für jedes Flag einen A/B-Regressionstest einführen.

### 6.4 Pumpenkosten werden in verschiedenen Tools unterschiedlich behandelt

Fundstellen:

- `scripts/paper/extract_artefacts.py`, etwa Zeilen 180–198
- `tools/economic_cost.py`, etwa Zeilen 29–36
- `tools/evaluator.py`, etwa Zeilen 450–467
- `tools/objective_decomposition.py`, etwa Zeilen 65–74

Der Extractor zieht Pumpenkosten aus `cost_energy_buy` ab und legt sie separat als `cost_pump_eur` ab. `economic_cost.py` und `evaluator.py` addieren diese separate Komponente nicht wieder hinzu. `objective_decomposition.py` tut es dagegen und behauptet gleichzeitig, seine Definition sei identisch zu `economic_cost.py`.

**Folge:** Für pumpenaktive Fälle können „economic cost“, Evaluator-Kosten und Objective Decomposition voneinander abweichen. Bei Kontrollen mit Pumpenkosten null bleibt der Headline-Wert möglicherweise unverändert; L3-/Evaluator-/Figure-Aussagen sind jedoch gefährdet.

**Erforderliche Codeänderung:** Eine einzige kanonische Kostenfunktion und ein versioniertes Ergebnisschema verwenden. Unit-Test mit `cost_pump_eur > 0` hinzufügen.

### 6.5 Paper-Skripte enthalten nicht portable Pfade und veraltete Annahmen

- `tools/objective_decomposition.py`, etwa Zeilen 53–55, referenziert hart einen externen Worktree `../paper1_faithful_c19d690`; die Eingaben fehlen lokal.
- `tools/economic_cost.py` beschreibt im Docstring den Residualterm noch als vom Return-Temperature-Regularizer dominiert; das widerspricht der neueren Zerlegung.
- Die aktuellen Kontrollkonfigurationen und Ergebnisdateien sind nicht im Repository auffindbar, obwohl die Paper-Skripte sie voraussetzen.

### 6.6 Reproduktionsumgebung ist nicht aus einem Guss

Die lokal vorhandenen Python-Umgebungen sind geteilt:

- Python 3.12: Gurobi, Pyomo, pandas, NumPy und Pydantic vorhanden; YAML, openpyxl und pytest fehlen.
- Conda-Umgebung: YAML, openpyxl und pytest vorhanden; Gurobi und Pyomo fehlen.

Für die Tests wurden die vorhandenen Site-Packages nur zur Laufzeit kombiniert; es wurde nichts installiert. Das zeigt, dass das Paket nicht mit einem einzigen dokumentierten Installationsschritt reproduzierbar ist.

`zenodo_paper_1/requirements.txt` deckt die tatsächlichen Laufzeit-/Testabhängigkeiten nicht vollständig ab. Eine gepinnte Environment-Datei bzw. Lock-Datei, ein dokumentierter Gurobi-Schritt und ein Clean-Environment-CI-Test fehlen.

### 6.7 Testpaket ist nicht grün

Gezielte lokale Testläufe ergaben:

- Modell-/Physiktests: **8 passed, 1 failed, 2 skipped**.
- Audit-Tests des alten Build-Pakets: **4 passed, 6 failed, 1 skipped**.

Details:

- `tests/test_model_finalizer_passthrough.py` scheitert, weil ein Test-Pipe-Objekt kein neues Attribut `.bidirectional` besitzt, das in `model_finalizer.py` etwa Zeile 386 ungeprüft verwendet wird.
- Mehrere Audit-Tests scheitern wegen fehlender `data/objective_decomposition.csv` und `data/synth_factorial_decomposition.csv`.
- Wichtige pandapipes-/Dispatch-Teile werden wegen fehlender Abhängigkeiten bzw. Daten übersprungen.

Ein grüner, aus dem veröffentlichten Paket ausführbarer Testlauf ist vor der Reproduzierbarkeitsbehauptung erforderlich.

## 7. Gurobi- und Smoke-Test-Protokoll

Gurobi ist installiert und lauffähig. Der anfängliche Lizenzfehler trat nur in der eingeschränkten Sandbox auf; außerhalb davon funktionierte die vorhandene Lizenz.

| Test | Ergebnis |
|---|---|
| Gurobi-Version/Lizenz | Gurobi 13.0.1, Academic License erkannt |
| Kleines LP | optimal, Status 2, Zielfunktionswert 1 |
| 4-h-Calion-End-to-End-Modell | optimal; 36 Zeilen, 25 Spalten, 4 Binärvariablen; Objective EUR 1,333.33; Gap 0 |
| 2-h-Netzmodell mit 1-km-Rohr | optimal; Netz aktiv; Verlust 0.075 MWh über 2 h |
| Physik-Flag-A/B-Test | Fehler reproduziert: Flags werden ignoriert |
| Storage-API-Test | Fehler reproduziert: Benutzerwerte werden durch Defaults ersetzt |
| Malformed-Topology-Test | Fehler reproduziert: stiller Rückfall auf globale Bilanz |

Beim 4-h-Lauf exportierte `optimize()` unerwartet automatisch fünf Ergebnisdateien unter `outputs/runs/thermal_network_results`, obwohl der Test als reiner Optimierungslauf gedacht war. Der exakte erzeugte Ordner wurde direkt geprüft und anschließend entfernt; es blieb keine persistente Änderung zurück. Diese Auto-Export-Nebenwirkung sollte per explizitem `export_results`-Flag steuerbar werden.

## 8. Konkrete Korrekturen für die Response Letter

Als Basis ausschließlich `response_letter_tightened.md` verwenden, danach:

1. Reviewer-Kommentare vollständig und wörtlich übernehmen.
2. Für jeden Punkt klar zwischen „implemented“, „partially addressed“ und „clarified as limitation“ unterscheiden.
3. Keine Zusage als erfüllt bezeichnen, bevor Manuskript, Code und Artefakt sie belegen.
4. Die offene Abschlusscheckliste um Zeilen 296–300 entfernen.
5. Alle Fundstellen erst nach dem finalen Build aktualisieren.

Veraltete Verweise in der Tightened-Version prüfen/ersetzen:

- R2.2: „Fig. F6“ → derzeit eher Fig. 4, Table 8 und §3.2.
- R2.3: „Fig. F13“ existiert nicht → derzeit Table 12 und §3.8.
- R2.4: „F11/corridor“ nicht auffindbar → derzeit Table 7, Fig. 3, §3.6 und Appendix A.
- R2.5: derzeit relevante Stellen Table 6, Table 13 und Figs. 6–7.
- R1.6: derzeit eher §3.4 und Table 10.

Inhaltlich zu korrigieren:

- Nicht behaupten, „regret“ sei entfernt, solange der Begriff im Paper zentral bleibt.
- Nicht behaupten, jede Leiterstufe füge exakt ein Phänomen hinzu.
- Nicht von sauberer 2×2-Identifikation sprechen, solange der Physics-/Configuration-Confound besteht.
- 72 h nicht als Woche bezeichnen.
- Nicht behaupten, jede nichtlineare Auswertung enthalte Incumbent, Bound und Effektintervall, solange die Tabelle diese Werte nicht zeigt.
- „QCP“ nur verwenden, wenn dies tatsächlich die gelöste Modellklasse ist.
- Nicht behaupten, alle Validierungsgrößen seien held-out oder empirisch gemessen.
- Nicht behaupten, Highlights und Graphical Abstract seien bereits resubmitted; Zukunftsform verwenden, bis die Dateien hochgeladen sind.
- Vier Hauptabschnitte nennen, nicht fünf.
- Baseline-Clustering nicht als Billing-Boundary-basiert bezeichnen, wenn es im Manuskript als manuell definiert beschrieben wird.
- Die L3+-Nomenklaturbrücke um L6 erweitern oder vollständig entfernen.
- Den angeblichen Build-Time-Citation-Lumping-Check nur erwähnen, wenn ein echtes Prüfskript vorhanden ist; `natbib` mit `sort&compress` ist kein solcher Check.

## 9. Empfohlene Reihenfolge der Überarbeitung

1. **Designentscheidung treffen:** echte physics-matched 2×2-Neuberechnung oder ehrliche Umrahmung als konfundierte Sensitivitätsanalyse.
2. **Evaluator-Scope entscheiden:** Code erweitern oder sämtliche High-Fidelity-/Regret-/Deliverability-Claims auf Valuation-Overlay-Niveau zurücknehmen.
3. **Validierung neu strukturieren:** Calibration, Verification und Validation klar trennen; Tabellen und Response Letter synchronisieren.
4. **Codefehler beheben:** Network-API-Schema, Physik-Flags, Storage-Keys, Fail-fast-Netzwerk und kanonische Pumpenkosten.
5. **Alle Ergebnisartefakte neu erzeugen:** Controls, Tabellen, Abbildungen, Rundungen und Supplement-Nummern aus einer einzigen Quelle.
6. **Tests aus sauberer Umgebung ausführen:** ein Installationspfad, Gurobi-Anleitung, alle relevanten Tests grün, keine stillen Skips.
7. **Neues Zenodo-Release publizieren:** vollständige Configs, Daten, Ergebnisse, Skripte, Figuren, Tabellen, Version und README.
8. **Overleaf-Paket finalisieren:** Bilder, Highlights, Graphical Abstract, Bibliographie, Kommentare/TODOs, Supplement-Titel.
9. **Response Letter zuletzt neu synchronisieren:** wörtliche Kommentare, korrekte Fundstellen, keine überzogenen Erfüllungsbehauptungen.
10. **Finaler Clean Build und Submission-Audit:** ausschließlich aus dem Overleaf-/Zenodo-Paket, idealerweise auf einem frischen Rechner oder CI-Runner.

## 10. Bereits überzeugende bzw. richtige Änderungen

- Die Kernfrage und der operationale Scope sind wesentlich klarer als in der alten Fassung.
- Die zentrale Verlust-vs.-Topologie-Botschaft wird durch mehrere zusätzliche Kontrollen grundsätzlich gestützt, auch wenn die kausale 2×2-Formulierung korrigiert werden muss.
- Die Storage-Cycling-Kosten und die Storage-Loss-Konvention wurden passend zum Modellcode ergänzt.
- Die dimensionsbezogene `10^6`-Korrektur bei der Loss Number ist richtig.
- Delay, nonlinear reference solves, Clustering, Supply-Temperature-Sweep, Solverzeiten und synthetische Tests erhöhen die Transparenz deutlich.
- Die Einschränkungen von Fixed-Schedule-Evaluationen werden an einzelnen Stellen bereits sehr gut formuliert; diese vorsichtige Sprache sollte paperweit übernommen werden.
- Abstract- und Conclusion-Format erfüllen die formalen Editorvorgaben.

## 11. Grenzen dieser Prüfung

- Auf dem Rechner ist keine lokale TeX-Distribution verfügbar; deshalb konnte kein neuer PDF-Clean-Build ausgeführt werden. Die statische Prüfung fand keine doppelten Labels oder offensichtlich undefinierten `\ref`-/`\cite`-Schlüssel, ersetzt aber keinen finalen Build.
- Die aktuellen Ergebnis-CSVs und Kontrollkonfigurationen fehlen. Headline-Zahlen konnten daher nicht vollständig aus Rohdaten neu berechnet werden.
- Einige pandapipes-/Paper-Tests wurden aufgrund fehlender Daten oder geteilter Python-Umgebungen übersprungen.
- Die Gurobi-Smoke-Tests belegen die grundsätzliche Solver- und Modelllauffähigkeit, nicht die vollständige Reproduktion der Jahresläufe.

## 12. Finale Reviewer-Empfehlung

Das Paper hat einen publizierbaren Kern, aber die derzeitige Fassung ist noch nicht versions-, artefakt- und claim-konsistent. Besonders die 2×2-Identifikation, die Bezeichnung der Forward-Evaluation als Regret/Entscheidungsnachweis, die Validierungsclaims und die Diskrepanz zwischen beschriebenem und implementiertem Evaluator müssen vor der Wiedereinreichung korrigiert werden. Werden diese Punkte eng und transparent gelöst, sollte sich die Arbeit gegenüber den Reviewern deutlich robuster verteidigen lassen.
