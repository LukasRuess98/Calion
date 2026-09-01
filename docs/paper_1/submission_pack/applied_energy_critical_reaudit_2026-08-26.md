# Kritischer Vollaudit der überarbeiteten Applied-Energy-Veröffentlichung

**Manuskript:** *Loss Visibility versus Spatial Detail in District-Heating Dispatch Optimisation*  
**Zieljournal:** *Applied Energy*  
**Stand der Prüfung:** 26.08.2026  
**Primärbasis:** aktuelles `main(1).tex`  
**Ergänzende Basis:** zuletzt kompilierte `paper_CLEAN.pdf` / `paper_MARKUP.pdf`, bisherige Korrekturprotokolle, Response Letter und erneute externe Literaturprüfung.

---

# 1. Gesamturteil

## Aktueller Status: **NO-GO für die sofortige Wiedereinreichung**

Die Arbeit ist gegenüber der ursprünglichen Einreichung **deutlich stärker**. Die wesentlichen Reviewer-Einwände wurden nicht nur sprachlich, sondern teilweise mit neuen Experimenten beantwortet. Besonders stark bleiben:

- der CP / CP+L / ND0 / L1-Kontrollgedanke,
- die 135 synthetischen Netze,
- die Trennung von Kostenbias und der Bewertung des erzeugten Schedules,
- die explizite Limitierung auf radial, zentral versorgt, fixed capacity und hourly dispatch,
- die Clustering-Sensitivität,
- die hydraulische Plausibilisierung über reale Pumpendaten, DXF-Lateralen und pandapipes,
- die nonlinear week re-solves mit Solver-Bounds,
- die inzwischen deutlich ehrlichere Behandlung der Sommer-Infeasibility.

**Trotzdem gibt es noch mehrere Punkte, die in einem zweiten Review sehr wahrscheinlich auffallen würden.**

Die wichtigsten verbleibenden Risiken sind nun:

1. Die Memmingen-Zerlegung wird weiterhin als **exact loss/topology decomposition** verkauft, obwohl CP und ND0 im tatsächlich gerechneten Stand zusätzlich in drei Nicht-Netzwerkparametern differieren.
2. Die Größe **decision regret** ist kein klassisches Regret gegenüber einem High-Fidelity-Optimum, sondern ein signierter L1-relativer Forward-Valuation-Gap.
3. Der Forward Evaluator ist im aktuellen Text keine vollständig physikalisch geschlossene „execution simulation“: Pumpstrom wird neu berechnet, aber Netzbezug bleibt fix, und thermischer Überschuss wird nicht gedumpt.
4. Station-Level L4/L5 werden weiterhin an mehreren Stellen so interpretiert, als seien die resultierenden Dispatch-Entscheidungen getestet worden, obwohl keine Reoptimierung erfolgte.
5. Die Beschreibung des nonlinear week reference widerspricht der bereits dokumentierten tatsächlichen Implementierung.
6. Mehrere sichtbare Gleichungen sind dimensionsfehlerhaft bzw. unvollständig.
7. Es sind weiterhin veraltete Zahlen und Formulierungen im aktuellen Source enthalten.
8. Die Literature Review enthält weiterhin relevante Lücken und mindestens drei sehr riskante Citation-to-Claim-Zuordnungen.
9. Der aktuelle hochgeladene `main(1).tex` ist nur ein Wrapper mit zahlreichen `\input{...}`-Dateien. Deshalb kann der **aktuellste Gesamtstand nicht vollständig kompiliert und auditiert werden**, solange diese Input-Dateien nicht im aktuellen Upload enthalten sind.
10. Die zuletzt kompilierte PDF ist älter als `main(1).tex`; Metadaten, Titel, Fonts und Response Letter sind dadurch nicht synchron.

---

# 2. Was seit der letzten Prüfung verbessert wurde

Mehrere frühere Blocker wurden im aktuellen `main(1).tex` sichtbar verbessert:

## 2.1 Distributed generation im Synthetic Factorial

**Verbessert.**

Der aktuelle Methodentext stellt nun klar, dass alle 135 synthetischen Netze zentral versorgt sind und distributed generation außerhalb des Scopes bleibt.

Das ist wesentlich sauberer als die frühere Behauptung eines central/distributed-Faktors.

---

## 2.2 ZN ist methodisch besser eingeordnet

**Verbessert.**

ZN wird nicht mehr implizit als gleichwertige Ladder-Stufe behandelt, sondern als Aggregation-Sensitivity-Experiment.

---

## 2.3 „True cost“ wurde im sichtbaren Haupttext weitgehend entschärft

**Verbessert.**

Der aktuelle Forward-Evaluator spricht von einem:

> forward-evaluated (policy-dependent) cost

und grenzt ihn gegen ein unberechnetes High-Fidelity-Optimum ab.

Das ist deutlich besser als die frühere „true cost“-Sprache.

---

## 2.4 Shortfall ist methodisch jetzt als Valuation Overlay beschrieben

**Verbessert.**

In §2.4 wird ausdrücklich gesagt:

- kein Redispatch,
- keine neue Commitment-Prüfung,
- keine Capacity-/Ramp-/CHP-Coupling-Reoptimierung,
- Shortfall wird über Preisannahmen bewertet.

Das ist methodisch ehrlich.

**Problem:** Der Results-Text widerspricht dieser sauberen Methodendefinition noch immer. Siehe P0.3.

---

## 2.5 L4/L5-Upper-Bound-Fehler wurde in der Methodik korrigiert

**Teilweise verbessert.**

Der Methodentext sagt inzwischen korrekt, dass die Forward Evaluation eines festen Schedules **kein Bound über alle reoptimierten Schedules** ist.

**Problem:** Abstract, Results und Implications transportieren teilweise weiterhin die alte Interpretation.

---

## 2.6 Summer nonlinear infeasibility wird vorsichtiger interpretiert

**Verbessert.**

Der aktuelle Text sagt ausdrücklich, dass nicht geklärt ist, ob die Summer-Infeasibility physikalisch oder numerisch/formulatorisch bedingt ist.

Diese Formulierung sollte unbedingt erhalten bleiben.

---

## 2.7 Held-out extrapolation wording wurde teilweise verbessert

Der aktuelle Source enthält inzwischen die präzisere Beschreibung der 30-km-Extrapolation und nennt den Screening-Charakter der Loss-Number-Beziehung.

Das ist besser als die frühere universelle „design rule“-Interpretation.

**Aber:** Figure caption und einige Implications verwenden weiterhin „design rule“ bzw. zu harte Übertragbarkeitsaussagen.

---

# 3. P0 - Submission-Blocker

# P0.1 Die Memmingen-Zerlegung ist nicht das reine 2×2-Loss/Topology-Experiment, als das sie weiterhin dargestellt wird

## Fundstellen

`main(1).tex`, insbesondere:

- §2.1 / Methodendesign
- §2.3
- §3.2, ca. Zeilen 679-708
- Figure decomposition caption
- Abstract

## Aktueller Widerspruch

Die Methodik beschreibt vier Controls:

- CP
- CP+L
- ND0
- L1

als sauberes 2×2-Faktorial:

- topology absent/present
- losses absent/present

und behauptet sinngemäß:

> no comparison is confounded

bzw.

> exact loss/topology decomposition.

Im Results-Teil wird inzwischen aber selbst offengelegt, dass:

> CP and ND0 differ also in three physics parameters  
> (return temperature, heating curve, heat-pump COP)

Der aktuelle Text sagt:

- as-run ND0 - CP = ca. 961 EUR = 4.7 % des Gaps
- nach zusätzlichem ND0-Run mit CP-Physics:
  - reine Topologie = ca. 52 EUR = 0.25 %
  - physics-parameter difference = ca. 909 EUR = 4.4 %

Das ist eine wichtige und gute Korrektur.

**Aber genau dadurch ist belegt, dass die vier ursprünglich gerechneten Memmingen-Controls kein sauberes 2×2 topology × loss factorial waren.**

## Warum das kritisch ist

Eine algebraisch exakt schließende Zerlegung ist nicht automatisch eine **kausal saubere Faktorisierung**.

Wenn neben dem Faktor topology gleichzeitig verändert werden:

- return temperature,
- heating curve,
- heat-pump COP,

ist die ursprüngliche Main-Effect-Zuordnung konfundiert.

Die nachträgliche 4.4-%-Zeile ist eine sinnvolle **Accounting-Korrektur**, aber sie macht den ursprünglichen Vier-Zellen-Versuch nicht rückwirkend zu einem reinen Faktorialexperiment.

## Aktuell irreführend

Besonders problematisch sind Formulierungen wie:

> the loss/topology decomposition is exact

> four decomposition controls form a 2 × 2 factorial

> no comparison is confounded

> exact decomposition of the copperplate-to-baseline cost gap

wenn nicht unmittelbar erläutert wird, dass Memmingen einen zusätzlichen Physics-Parameter-Term benötigt.

## Empfohlene Lösung A - wissenschaftlich sauberste Lösung

Beim ohnehin noch offenen kleinen Re-Run:

**CP, CP+L, ND0, L1 vollständig mit identischen Nicht-Faktor-Parametern rechnen.**

Dabei müssen insbesondere harmonisiert sein:

- heating curve,
- return temperature assumptions,
- heat-pump COP treatment,
- cost objective,
- alle weiteren Asset- und Accounting-Annahmen.

Dann liegt tatsächlich ein reines:

\[
2 \times 2: \quad \text{topology} \times \text{loss visibility}
\]

vor.

Das wäre die stärkste Version des Papers.

## Lösung B - falls kein neuer Run möglich ist

Dann methodisch umbenennen:

> extended accounting decomposition of the Memmingen cost gap

und klar sagen:

- das **synthetische 135er-Faktorial** liefert die saubere topology/loss-Causal-Evidence,
- Memmingen liefert eine reale Fallstudien-Zerlegung mit zusätzlichem Physics-Parameter-Term.

### Wichtig

Die 0.25-%-Topologiezahl ist sehr stark. Sie muss nur korrekt beschrieben werden.

---

# P0.2 „Decision regret“ ist terminologisch und mathematisch angreifbar

## Fundstelle

§2.4, ca. Zeilen 390-400.

Der Text definiert:

> decision regret as the difference between the forward-evaluated costs of the two schedules

und sagt anschließend selbst:

> measured against the baseline schedule's forward-evaluated cost, not against the (uncomputed) high-fidelity optimum.

Das ist transparent.

## Problem

Ein klassisches Regret-Konzept misst typischerweise den Abstand einer Entscheidung zum bestmöglichen/reference-optimalen Ergebnis unter dem Bewertungsmodell.

Eure Größe ist dagegen:

- relativ zu L1,
- signiert,
- kann negativ werden,
- basiert nicht auf einem High-Fidelity-Optimum.

CP+L liegt z. B. bei ungefähr -0.54 %.

Ein negatives „regret“ ist terminologisch ungewöhnlich und kann Reviewer 2 erneut eine Angriffsfläche geben.

Auch die Analogie zur **Value of the Stochastic Solution** ist nur eingeschränkt passend, weil VSS einen wohldefinierten Vergleich mit einer optimierten Referenzlösung beinhaltet.

## Empfehlung

### Beste Lösung

Die Größe umbenennen in z. B.:

- **forward-valued schedule gap**
- **reference-valued schedule gap**
- **forward-evaluated decision gap**

und `decision regret` nur als informelle Interpretation verwenden.

### Alternativ

Falls `decision regret` unbedingt behalten werden soll:

bereits in Abstract und Methodik definieren als:

> signed L1-relative decision-regret proxy

oder:

> L1-relative forward regret

und ausdrücklich sagen:

> It is not regret relative to the optimum of the high-fidelity model and may therefore take negative values.

## Warum dies jetzt leicht lösbar ist

Der neue Titel enthält „Decision Regret“ nicht mehr. Eine Umbenennung würde also keinen großen Umbau mehr erfordern.

---

# P0.3 Methodik und Results widersprechen sich beim Shortfall

## Methodik

§2.4 sagt korrekt:

- Shortfall wird **nicht physisch redispatched**,
- keine Capacity-/Commitment-/Ramp-Reoptimierung,
- drei Preis-Overlays,
- daher keine executable recourse simulation.

## Results

§3.3 sagt dagegen:

> the loss the copperplate omits must be covered under execution by topping up at the marginal or peak unit

und:

> topping up at the marginal unit

sowie:

> the 46 % regret being that substitution priced.

Das klingt wie ein tatsächlich simulierter physischer Redispatch.

## Das ist sachlich inkonsistent

Ihr habt im Methodenteil selbst korrekt beschrieben, dass **kein Topping-up simuliert wird**.

## Ersetzen durch

> the shortfall is valued at the marginal replacement-cost assumption

und entsprechend:

> valued at the peak-unit cost assumption

statt:

> topped up at the peak unit.

## Konsequenz

Auch die Formulierung:

> hydraucially deliverable

sollte nur dort verwendet werden, wo wirklich eine vollständige physikalische Feasibility-Prüfung erfolgt.

---

# P0.4 Der Forward Evaluator ist derzeit keine vollständig energiegeschlossene Execution Simulation

Dies ist ein **neuer, sehr wichtiger Fund**.

## Fundstelle

§2.4, ca. Zeilen 406-430.

Der Text sagt:

- grid imports and exports werden als First-Stage-Entscheidungen fixiert,
- pumping power wird unter High-Fidelity-Physics neu berechnet,
- neuer Pumpstrom wird bepreist,
- **grid import wird aber nicht angepasst**.

Wörtlich:

> Recomputed pumping power is priced at the electricity tariff and added to the reported cost without adjusting the fixed grid import.

## Problem 1: elektrische Energiebilanz

Wenn:

- Netzbezug fix bleibt,
- Pumpstrom sich ändert,

dann ist die elektrische Bilanz nicht mehr zwangsläufig geschlossen.

Das ist als **Accounting Overlay** zulässig.

Es ist aber keine vollständig ausführbare Simulation des fixen Dispatches.

## Problem 2: thermischer Überschuss

Der Text sagt außerdem:

> If recomputed native losses are lower than scheduled losses, the surplus receives no value and no additional dumping is introduced.

Wenn Erzeugung, Storage und Dumping fix sind, aber der physikalische Verlust sinkt, entsteht ein thermischer Überschuss.

Dieser muss physikalisch:

- gedumpt,
- abgeregelt,
- gespeichert,
- oder anderweitig bilanziert werden.

„No additional dumping“ bedeutet daher ebenfalls, dass die Forward Evaluation nicht als vollständig geschlossene physische Execution Simulation interpretiert werden darf.

## Konsequenz

Der Evaluator ist besser zu beschreiben als:

> higher-fidelity state reconstruction and cost-valuation overlay

anstatt als:

> simulator of executing the schedule.

## Zwei mögliche Lösungen

### Lösung A - Evaluator wirklich physikalisch schließen

- Pumpstromdelta in Netzbezug einrechnen.
- Bei geringerem Verlust zusätzliche Dump-/Curtailment-Energie erfassen.
- Bei höherem Verlust Shortfall explizit ausweisen.
- Asset-Schedule selbst weiterhin fix lassen.

Das wäre noch kein Redispatch, aber die Energieflüsse wären geschlossen.

### Lösung B - Claim reduzieren

Dann überall klar schreiben:

> accounting and feasibility overlay on a fixed dispatch

und keine vollständige „physical deliverability“ behaupten.

---

# P0.5 „Hydraulically deliverable“ ist zu breit

## Abstract / Results

Es wird gesagt, loss-aware schedules seien:

> hydraulically deliverable

bzw.

> Physical deliverability is checked directly.

## Tatsächlich geprüft werden

nach aktuellem Text insbesondere:

- velocity,
- differential pressure,
- heat shortfall.

Aber:

- elektrische Bilanz wird im Forward Overlay nicht vollständig nachgeführt,
- Shortfall-Valuation ist keine Recourse Simulation,
- Station-/Lateralhydraulik ist nicht im independent pandapipes reference enthalten,
- Node temperatures sind messtechnisch nicht vollständig validiert.

## Sicherer Claim

> No velocity, differential-pressure, or heat-shortfall violation was identified for the loss-aware schedules under the forward checks.

Das ist präzise und stark genug.

---

# P0.6 L4/L5 werden weiterhin zu stark interpretiert

## Methodik inzwischen besser

§2.6.1 erkennt an:

> forward evaluation ... does not establish a bound over re-optimised schedules.

Gut.

## Aber weiterhin problematisch

### Abstract

> station-resolved hydraulics ... suggesting limited re-optimisation value

Nicht getestet.

### Results

§3.6:

> The station-resolved hydraulics change dispatch negligibly.

und:

> station-level hydraulics move dispatch cost by <1 % and dispatch decisions by ≈0

Das ist nicht belegt.

Es gab **keine station-level re-optimisation**.

### Implications

> station-resolved hydraulics ... changes dispatch cost by little and dispatch decisions by less

ebenfalls zu stark.

## Korrekte Formulierung

> Applying station-resolved hydraulics to the fixed L1 schedule increases its forward-evaluated cost by less than 1% and reveals no additional hydraulic violation. The corresponding re-optimised dispatch effect was not evaluated.

## Wichtig

Station-Level-Hydraulik wird außerdem **nicht über die 135 synthetischen Netze** getestet.

Der „null at maximal fidelity“-Claim ist deshalb eine **Ein-Fall-Beobachtung**, kein generalisiertes Ergebnis.

---

# P0.7 Aktuelle Beschreibung des nonlinear reference widerspricht dem dokumentierten tatsächlichen Run

## Fundstelle

§3.8, ca. Zeilen 885-905.

Aktueller Source:

> The resulting model restores exponential temperature decay and the heat-loss bilinearities.

und:

> native nonlinear physics is marginally cheaper.

## Widerspruch

Die bisherige technische Audit-Historie hatte aus den Solver-/Code-Records ergeben:

- der bilinear temperature-decay product wird wiederhergestellt,
- der exponential decay factor bleibt PWL,
- weekly reference ist daher **nicht vollständig native exponential physics**.

Dieser Punkt war bereits als explizite Korrektur dokumentiert.

## Daher jetzt zwingend

Vor Submission gegen die tatsächliche aktuelle Implementierung / Solver-Konfiguration prüfen:

### Falls der bisherige Audit korrekt ist

Dann schreiben:

> The weekly nonlinear reference restores the bilinear temperature-decay coupling while retaining the common PWL approximation of the exponential decay factor.

und nicht:

> restores exponential temperature decay.

### Falls der Code inzwischen geändert wurde

Dann muss:

- der neue Run eindeutig belegt,
- der Solveraufbau beschrieben,
- Figure/Table neu synchronisiert werden.

## Zusätzlich fehlt

Die zwei 72-h-Windows werden als:

> representative winter and autumn windows

bezeichnet.

Reviewer 2 hatte explizit eine nachvollziehbare Auswahl verlangt.

Angeben:

- konkrete Kalenderdaten,
- Auswahlkriterium,
- warum diese Windows repräsentativ sind.

---

# P0.8 Sichtbare Gleichung zur Supply-Temperature-Sensitivity ist dimensionsfalsch

## Fundstelle

§3.7:

\[
Q = \dot m (T_\mathrm{sup}-T_\mathrm{ret})
\]

## Problem

Es fehlt mindestens:

\[
c_p
\]

und je nach Einheitenkonvention ein MW-Konversionsfaktor.

Korrekt z. B.:

\[
Q = \dot m c_p (T_\mathrm{sup}-T_\mathrm{ret})
\]

mit explizit konsistenter Einheitendefinition.

Das ist ein einfacher, aber sehr sichtbarer Formelfehler.

---

# P0.9 CP+L-Loss-Adder-Gleichung ist dimensionsseitig unvollständig

## Fundstelle

§2.3:

\[
L_b(t)
= \sum_p U_p \ell_p(T_\mathrm{sup}-T_g)
+ \sum_p U^r_p \ell_p(T_\mathrm{ret}-T_g)
\]

Bei:

- \(U\) in W/(m K),
- \(\ell\) in m,
- Temperaturdifferenz in K,

ergibt die Summe **W**.

Wenn \(L_b\) in der thermischen MW-Bilanz verwendet wird, fehlt:

\[
10^{-6}.
\]

## Zusätzlich

Im übrigen Modell ist Ground Temperature zeitabhängig.

Hier steht \(T_g\) ohne \(t\).

Klären:

- konstant?
- Jahresmittel?
- oder eigentlich \(T_g(t)\)?

---

# P0.10 Loss-number-Formel ist ebenfalls dimensions- und zeitlich unklar

## Fundstelle

§3.9:

\[
\lambda =
\left(
\sum U^s L(T_\mathrm{sup}-T_g)
+
\sum U^r L(T_\mathrm{ret}-T_g)
\right)
8760 /
\mathrm{demand}
\]

## Probleme

### 1. Einheit

Bei W-basiertem \(U\) ist eine W→MW/MWh-Konversion nötig.

### 2. Zeitabhängigkeit

Das Modell selbst hat:

- heating curve,
- time-varying supply/return temperatures,
- ground temperature.

Die Formel multipliziert einen scheinbar konstanten Verlust mit 8760 h.

Wenn tatsächlich Jahresmittelwerte eingesetzt werden:

**explizit sagen.**

Methodisch sauberer:

\[
\lambda =
\frac{
\sum_t \Delta t \,
10^{-6}
\sum_p
\left[
U_p^sL_p(T_{\mathrm{sup},t}-T_{g,t})
+
U_p^rL_p(T_{\mathrm{ret},t}-T_{g,t})
\right]
}{
E_\mathrm{demand}
}.
\]

Dann entspricht die Definition wirklich:

> annual loss / annual demand.

---

# P0.11 Transport-delay-Rundung: bekannter früherer mathematischer Fehler muss im aktuellen Input verifiziert werden

Die zuletzt kompilierte PDF enthielt:

\[
k_p = \mathrm{round}(\tau_p/\Delta t)
\]

und gleichzeitig:

- längste Reisezeit ca. 35 min,
- daher \(k_p=0\).

Das ist widersprüchlich:

\[
\mathrm{round}(35/60)=1.
\]

Der frühere Audit hatte deshalb korrekt empfohlen:

\[
k_p = \left\lfloor \tau_p/\Delta t \right\rfloor
\]

bzw. explizit:

> sub-hourly delays are not represented on the hourly grid.

## Aktueller Status

Die entsprechende Gleichung liegt im externen:

`extended_physics_v2.tex`

und ist im aktuellen Upload **nicht enthalten**.

Daher kann nicht verifiziert werden, ob dieser Fehler inzwischen wirklich behoben wurde.

### P0 vor Einreichung

Prüfen und final kompilieren.

---

# P0.12 Numerische Altwerte sind weiterhin im aktuellen Source

## Besonders auffällig: 81.2 %

Aktueller Source §3.9:

> loss burden ranges from 3.2 % to 81.2 %

In der bisherigen Korrekturhistorie war dieser Wert bereits als veraltet/falsch identifiziert und auf **67.4 %** korrigiert worden.

Das bedeutet:

**Der aktuelle Source hat offenbar einen alten Wert wieder aufgenommen.**

## Weitere Konsistenzprüfungen

Unbedingt aus einer einzigen Results-Datei neu generieren:

- loss burden min/max,
- 95.8 % loss share,
- 0.25 % topology proper,
- 4.4 % physics parameter,
- -0.5 % interaction,
- held-out MAPE,
- 30-km error,
- 1.4 % pressure/pumping,
- 4.6 % Tsup sensitivity,
- weekly nonlinear values,
- solve gaps.

---

# P0.13 Optimality gap synthetic: 0.01 % vs. 0.1 %

Die Methodik nennt für die Full-Network-Solves an einer Stelle sinngemäß dieselbe **0.01-%-Toleranz** wie beim Realfall.

§3.2 sagt dagegen für die 135 synthetischen Netze:

> all solves at ≤0.1 % optimality gap.

Das muss vereinheitlicht werden.

Falls:

- Real case: 0.01 %
- Synthetic: 0.1 %

dann genau so überall schreiben.

---

# P0.14 Literature Review ist trotz Verbesserungen weiterhin unvollständig

Die externe Literaturprüfung bestätigt erneut drei Arbeiten von 2025, die sehr nah an eurem Beitrag liegen und in der aktuellen Literaturpositionierung berücksichtigt werden sollten.

## A. Vrain et al. (2025) - zwingend einordnen

**Vrain, M. et al.**  
*An aggregation method to model district heating networks in large-scale multi-energy simulations*  
Energy 334, 137384.  
DOI: 10.1016/j.energy.2025.137384

Warum relevant:

- explizite DHN-Aggregation,
- eigene aggregation-error metric,
- Prüfung physikalisch unzulässiger/inkonsistenter Aggregationslösungen,
- nicht nur objective-value comparison.

### Konsequenz

Zu breit:

> existing studies evaluate fidelity only by objective values

oder:

> none evaluates the resulting decisions.

Besser:

> Prior work has begun to test whether aggregated DHN decisions remain admissible when mapped back to more detailed representations. What remains missing is a common-reference monetary schedule valuation combined with an explicit separation of loss visibility from spatial routing.

---

## B. Cassetti et al. (2025) - zwingend einordnen

**Cassetti, L. A. et al.**  
*Impact of spatial resolution in modelling decarbonized district heating networks*  
Energy 334, 137357.  
DOI: 10.1016/j.energy.2025.137357

Untersucht direkt:

- spatial resolution,
- topology,
- costs,
- computation time.

### Konsequenz

Die alte Argumentation:

> closest evidence comes from a neighbouring field: electricity systems

ist 2026 nicht mehr aktuell.

Cassetti muss vor der Electricity-System-Analogie eingeordnet werden.

---

## C. Friedrich et al. (2025) - zwingend einordnen

**Friedrich, P.; Huynh, T.; Niessen, S.**  
*Optimizing district heating operations: Network modeling and its implications on system efficiency and operation*  
Smart Energy 18, 100175.  
DOI: 10.1016/j.segy.2025.100175

Sehr relevant, weil:

- linear vs nonlinear DH operational planning,
- unterschiedliche Network Models,
- Schedules werden anschließend in Modelica physikalisch simuliert,
- explizite Operational Feasibility.

### Konsequenz

Nicht behaupten, dass das Prüfen vereinfachter Schedules unter reicherer Physik grundsätzlich neu ist.

Eure verbleibende Novelty ist spezifischer und überzeugender:

1. **loss visibility vs spatial routing separation**
2. **common-reference monetary valuation of the fixed schedule**
3. **real + balanced synthetic transferability evidence**

---

# P0.15 Mindestens drei Citation-to-Claim-Paarungen bleiben hochriskant

## Bünning et al.

Aktueller Claim sinngemäß:

> zone-based model captures 85-95 % of dynamic temperature variation.

Die zitierte Arbeit zu bidirectional low-temperature district energy systems und agent-based control unterstützt diesen spezifischen Aggregationsclaim nach bisheriger Prüfung nicht eindeutig.

**Volltext prüfen oder Claim/Zitat ersetzen.**

---

## Leitner et al.

Aktueller Claim sinngemäß:

> copperplate vs full-graph produces 3-8 % cost differences.

Die zitierte Arbeit ist primär eine thermo-hydraulische/electric co-simulation zur P2H-Bewertung.

Der konkrete 3-8-%-Copperplate-vs-Full-Graph-Claim konnte bisher nicht verifiziert werden.

**Volltext prüfen oder Quelle ersetzen.**

---

## Giraud et al.

Wurde für eine Aussage wie:

> full-graph annual hourly models remain tractable to around a hundred nodes

herangezogen.

Die verfügbare Modelica-Library-Arbeit demonstriert keine entsprechende ~100-node × 8760-h MILP-Traktabilität.

**Claim streichen oder belastbare Quelle einsetzen.**

---

# 4. P1 - wichtige methodische Risiken

# P1.1 Objective alignment bleibt ein sinnvoller gezielter Sensitivity Run

Der aktuelle Schedule wird unter einer augmentierten Solver Objective erzeugt.

Die berichtete Economic Cost ist nicht vollständig identisch mit dieser Objective.

Auch wenn die Cost-Decomposition nachträglich auf Economic Cost basiert, können die zusätzlichen Objective-Terme die **Schedule-Selektion** verändern.

## Empfohlener gezielter Run

Beim ohnehin empfohlenen Vier-Fall-Run:

- CP
- CP+L
- ND0
- L1

gleichzeitig:

1. Nicht-Faktor-Physics harmonisieren,
2. Solver Objective exakt auf die berichtete Economic Cost ausrichten.

Damit könnt ihr **zwei zentrale Reviewer-Risiken mit nur einem kleinen Batch** schließen.

---

# P1.2 „Validated forward model“ ist noch zu stark

Im aktuellen Text wird der Forward Model mehrfach als:

> validated forward model

bezeichnet.

Tatsächlich gibt es verschiedene Evidenztypen:

## Field-data validation

- annual delivered energy / annual loss
- source-side measured quantities in Grenzen

## Computational verification

- agreement with pandapipes on trunk pressure
- self-consistency against exported model loss

## Nicht direkt validierbar

- primary junction temperatures hinter Mixing-Valve-Metering
- post-upgrade asset dispatch
- station/lateral hydraulics im Feld

## Empfehlung

Terminologisch trennen:

- **measurement-validated aggregate transport quantities**
- **computationally cross-checked hydraulic calculation**
- **higher-fidelity forward evaluator**

nicht pauschal:

> validated nonlinear reference.

---

# P1.3 Pandapipes bestätigt nicht die Station-Hydraulik

Der aktuelle Results-Text ist hier schon deutlich besser und sagt, dass pandapipes nur die trunk-pressure calculation prüft.

Diese Präzisierung sollte auch in:

- Abstract,
- Contribution statement,
- Reviewer response,
- Methods

durchgezogen werden.

Pump datasheets sind **Parameterbasis**, keine Validierung der station-level pressure model response.

---

# P1.4 MAPE ist keine Unsicherheitsbandbreite

§3.6:

> Propagating the 33.8 % source-flow uncertainty ...

Hier wird die **33.8-%-Flow-MAPE** offenbar als Unsicherheit interpretiert und auf Pump Power übertragen.

Das ist statistisch problematisch.

MAPE ist:

- ein Error Metric,
- keine Konfidenzbandbreite,
- keine symmetrische Unsicherheit.

## Besser

Wenn ihr ±33.8 % als deterministische Stress-Sensitivity rechnen wollt:

> Applying a ±33.8% deterministic flow perturbation, chosen to match the aggregate MAPE magnitude, ...

Aber nicht:

> propagating the 33.8% uncertainty.

Noch besser:

- empirical residual distribution,
- load-band-specific residuals,
- bootstrap / quantile sensitivity.

---

# P1.5 Pump-energy share wird möglicherweise mit einer nicht vergleichbaren Literaturgröße verglichen

Aktueller Text:

> pump-energy share = 0.080 % of thermal demand

und dann:

> below the 1-5 % transmission-network literature range.

Frühere Literaturbeschreibung lautete jedoch eher:

> pumping costs span 1-5 % of thermal energy cost.

Das sind unterschiedliche Größen:

- energy/energy
- cost/cost

Vor Submission exakt prüfen, was die zitierte Quelle tatsächlich berichtet.

Nur dimensionsgleiche Kennzahlen vergleichen.

---

# P1.6 Flexible supply-temperature sensitivity ist keine Dispatch-Optimierung

Die Methodik sagt korrekt:

- Forward Sweep,
- fixed demand,
- fixed return temperature,
- no reoptimised dispatch.

Trotzdem wird später formuliert:

> hydraulics determine the lowest-cost point

und in den Implications:

> flexible supply temperature changes dispatch cost by little and dispatch decisions by less.

## Probleme

- 4.6 % Cost Change ist nicht offensichtlich „little“.
- Dispatch decisions wurden nicht neu optimiert.
- 17.5 K ist nur der **lowest-cost tested point**, kein continuous optimum.

## Safer wording

> In the tested forward sensitivity, the lowest evaluated cost occurs at a 17.5 K reduction.

und:

> The sensitivity indicates that hydraulic constraints can become binding when supply temperature is lowered.

---

# P1.7 Loss-number Screening Heuristic weiterhin vorsichtiger formulieren

Positiv:

Der Text sagt inzwischen teilweise:

> first-order screening heuristic

und nennt judgmental thresholds.

Negativ:

Figure caption heißt noch:

> Fidelity design rule.

Implications sprechen von:

> threshold at which a lumped representation is likely safe.

## Empfehlung

Durchgehend:

- **screening relation**
- **screening heuristic**
- **illustrative regions**
- **not validated decision thresholds**

Kein:

- rule,
- safe threshold,
- transferable law.

---

# P1.8 „Memmingen measured 15 %“ ist falsch/zu stark

§3.9 sagt:

> its 11 % predicted burden close to the 15 % measured.

Die 15 % sind kein direkt gemessener Feldwert.

Es handelt sich um:

- modellbasierte Economic-Cost-Differenz / observed computational result.

Besser:

> close to the 15.1% modelled economic-cost gap.

---

# P1.9 „Residual is informative rather than error“ ist zu kausal

§3.9:

> The residual few points are informative rather than error: they are consistent with the omitted topology main effect and accounting difference ...

Das ist eher eine plausible Interpretation als ein Nachweis.

Besser:

> may partly reflect ...

oder:

> is of the same order as ...

---

# P1.10 „for most operators“ ist nicht belegt

Implications:

> for most operators the node or zone level is the finest defensible level.

Ihr habt einen konkreten Metering-Fall untersucht.

Daraus kann nicht generalisiert werden, was für **most operators** gilt.

Besser:

> for operators with comparable metering architectures ...

---

# P1.11 „standard planning setting“ ist unnötig stark

Limitations:

> this regime is not a corner case but the standard planning setting

Das ist eine unbelegte Feldbehauptung.

Besser:

> a common operational-planning setting

oder:

> the planning setting considered here.

---

# P1.12 „Conclusions do not depend on a measurement-accurate absolute schedule“ ist zu absolut

Limitations:

> they do not depend on a measurement-accurate absolute schedule.

Der Comparative Design reduziert die Sensitivität gegenüber gemeinsamen Modellfehlern.

Aber:

- Asset dispatch beeinflusst Flows,
- nonlinear losses,
- hydraulic states,
- storage timing,
- CHP/HP interactions.

Daher keine mathematische Invarianz.

Besser:

> the comparative design reduces, but does not eliminate, sensitivity to errors in the absolute post-upgrade dispatch trajectory.

---

# P1.13 „never a copperplate“ muss raus

§3.3 endet mit:

> never a copperplate.

Das ist:

- zu absolut,
- widerspricht eurer eigenen CP+L-Erkenntnis,
- unnötig polemisch.

Eure eigene Studie zeigt ja gerade:

Ein lumped model **kann** funktionieren, wenn die Losses korrekt und transferierbar vorgegeben werden.

Besser:

> A loss-blind copperplate should therefore not be used for scheduling within the tested regime unless its omitted network-loss burden is represented separately.

---

# P1.14 „incompetent controller“ ist im Source noch vorhanden

Auch wenn es teilweise nur in Comments / Contributions steht, ist diese Sprache für ein Top-Journal unnötig aggressiv.

Aktueller Source enthält weiterhin:

> incompetent controller

Diese Formulierung sollte aus sichtbarem Text und idealerweise auch aus Submission-Source-Kommentaren entfernt werden.

---

# 5. Literaturprüfung - aktualisierte Bewertung

## Gesamturteil Literature Review

**Struktur: gut.  
Aktualität und Novelty-Abgrenzung: noch nicht ausreichend.**

Die Review-Logik ist sinnvoll:

1. aggregation / spatial detail,
2. thermo-hydraulic fidelity,
3. decision-oriented assessment,
4. generation-side operational optimisation.

Aber 2025 sind mehrere Arbeiten erschienen, die eure bisherige Gap-Argumentation enger machen.

## Zwingend einordnen

### Vrain et al. 2025
DOI: `10.1016/j.energy.2025.137384`

### Cassetti et al. 2025
DOI: `10.1016/j.energy.2025.137357`

### Friedrich et al. 2025
DOI: `10.1016/j.segy.2025.100175`

## Neue, robustere Novelty-Formulierung

Empfohlen:

> Recent work has begun to examine the admissibility and operational consequences of aggregated or simplified district-heating models. However, two issues remain insufficiently separated: the monetary consequence of committing to a simplified schedule under a common richer reference, and the confounding of spatial routing with thermal-loss visibility. This study addresses these two gaps through a forward-valued schedule comparison and a controlled loss-versus-topology experiment.

Falls `decision regret` umbenannt wird, ist diese Formulierung besonders sauber.

---

# 6. Kapitelweise Kurzprüfung

# Abstract

## Noch ändern

- „one-phenomenon-at-a-time fidelity ladder“ relativieren.
- 95.8 % / 0.25 % nicht ohne 4.4-%-Physics-Term darstellen, wenn Memmingen gemeint ist.
- „hydraulically deliverable“ präzisieren.
- „suggesting limited re-optimisation value“ bei L4/L5 streichen.
- „Spatial routing is immaterial“ → „was negligible in the tested centrally supplied cases“.
- Entscheidung, ob `decision regret` umbenannt wird.

---

# Introduction / Literature Review

## Noch ändern

- Vrain 2025 ergänzen.
- Cassetti 2025 ergänzen.
- Friedrich 2025 ergänzen.
- „closest evidence from electricity systems“ aktualisieren.
- Broad „no prior study“-Claims eingrenzen.
- Bünning / Leitner / Giraud Claims gegen Originalvolltext verifizieren.
- „incompetent controller“ entfernen.
- Contribution „station detail changes decisions by zero“ korrigieren.

---

# Methods

## Noch ändern

- Memmingen Controls nicht als clean 2×2 verkaufen, solange Physics nicht harmonisiert ist.
- CP+L nicht „linear program“ nennen, sofern Binaries bestehen.
- CP+L Unit Conversion ergänzen.
- Forward Evaluator als valuation/state-reconstruction overlay präzisieren.
- elektrische und thermische Balance im Forward Overlay entweder schließen oder Claim reduzieren.
- `decision regret` Terminologie entscheiden.
- „validated“ vs „verified“ trennen.
- nonlinear-week actual physics gegen Code/Logs prüfen.
- versteckten Delay floor/round-Fehler im externen Input prüfen.
- external equations aus `base_formulation_v2` / `extended_physics_v2` erneut unit-auditen.

---

# Results

## Noch ändern

- Results-Shortfall-Prosa mit Methodik synchronisieren.
- „topping up“ entfernen.
- „never a copperplate“ entfernen.
- L4/L5 decision-change claims entfernen.
- MAPE nicht als uncertainty bezeichnen.
- pump-energy literature comparison prüfen.
- Tsup equation korrigieren.
- 81.2-%-Altwert korrigieren.
- nonlinear reference wording korrigieren.
- exact 72-h dates/selection criteria nennen.
- `measured 15%` korrigieren.
- screening rule → heuristic.

---

# Implications

## Noch ändern

- kein „Zeroth“; stilistisch besser mit klarer Priorisierung beginnen.
- „what a model must capture is loss, not graph“ auf tested regime begrenzen.
- „for most operators“ streichen.
- flexible-T result nicht als kleine Dispatch-Änderung darstellen.
- station-level decision claims korrigieren.
- keine „safe threshold“-Sprache.

---

# Limitations

## Noch ändern

- „standard planning setting“ → „common planning setting“.
- keine Invarianz gegenüber unvalidiertem absolute dispatch behaupten.
- klar sagen, dass station-level forward result ein Realfall-Ergebnis ist.
- objective-alignment sensitivity als noch offene Sensitivity aufnehmen, bis gerechnet.

---

# Conclusions

Die Conclusions liegen in einem externen `conclusions_v2.tex`, das im aktuellen Upload nicht enthalten ist.

**Deshalb kann der neueste Conclusion-Stand aktuell nicht vollständig geprüft werden.**

Zwingend darin suchen nach:

- universal loss-dominance claims,
- decision-regret terminology,
- L4/L5 decision claims,
- „under 1 %“ vs 1.4 % trunk hydraulics,
- 81.2 %,
- design-rule wording,
- “true/native physics”,
- distributed generation,
- “all networks / general / universal”.

---

# 7. Source-/Submission-Package-Probleme

# 7.1 Aktueller Upload ist kein vollständiger kompilierbarer Source-Stand

`main(1).tex` enthält zahlreiche externe Inputs, u. a.:

- `base_formulation_v2`
- `related_work_v2`
- `extended_physics_v2`
- `validation_results_v2`
- `conclusions_v2`
- `limitations_v2`
- diverse Tabellen.

Diese aktuellen Dateien liegen im Upload nicht vollständig vor.

## Konsequenz

Die Prüfung kann:

- den sichtbaren Wrapper,
- den früheren kompilierten PDF-Stand,
- und die dokumentierten Korrekturen

kombinieren.

Sie kann aber **nicht garantieren**, dass alle neuesten Input-Dateien synchron korrigiert sind.

### Vor Submission

Einmal den **vollständigen finalen LaTeX-Ordner** hochladen und daraus final kompilieren.

---

# 7.2 Letzte Clean-PDF ist veraltet

`paper_CLEAN.pdf` wurde am **19.08.2026** erzeugt.

Der aktuelle `main(1).tex` enthält bereits einen anderen Titel und weitere Änderungen.

## PDF-Metadaten aktuell noch alt

Die PDF trägt weiterhin:

> Estimation Bias versus Decision Regret in District-Heating Dispatch Optimisation

während `main(1).tex` aktuell lautet:

> Loss Visibility versus Spatial Detail in District-Heating Dispatch Optimisation

Vor Submission müssen synchron sein:

- PDF title,
- manuscript title page,
- Editorial Manager title,
- graphical abstract,
- highlights,
- response letter.

---

# 7.3 Type-3-Fonts in der letzten PDF

Die Preflight-Prüfung der letzten Clean-PDF zeigt zahlreiche Type-3-Fonts, insbesondere in eingebetteten Figure-Elementen.

Das ist kein wissenschaftlicher Blocker, aber für eine hochwertige Elsevier-Produktion suboptimal.

## Empfehlung

Figures erneut als Vektor-PDF mit eingebetteten TrueType/Type-1-Fonts erzeugen.

Bei Matplotlib typischerweise:

```python
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
```

Danach erneut:

```bash
pdffonts paper_CLEAN.pdf
```

prüfen.

---

# 7.4 Interne Draft-Kommentare aus finalem Source entfernen

Der aktuelle `main(1).tex` enthält weiterhin zahlreiche interne Kommentare:

- `DRAFTED`
- TODOs
- Reviewer-interne Argumentation
- alte Results-Herkunft
- „incompetent controller“
- Implementierungsnotizen
- companion-study planning.

Diese Kommentare rendern zwar nicht, aber Elsevier verlangt Source Files.

Für die finale Source-Einreichung sollte der Code professionell bereinigt werden.

---

# 7.5 Cross-reference-Check nötig

Beispiel im aktuellen Source:

> S\ref{subsec:generalis}

Das ist wahrscheinlich kein sauberer Section-Verweis.

Ebenso referenziert der Wrapper Labels, die möglicherweise nur in den externen Input-Files existieren.

Final nach Kompilierung prüfen:

- `??`
- undefined references
- multiply defined labels
- falsche `S`-Präfixe
- Table/Figure numbering
- Supplementary-vs-main references.

---

# 8. Response Letter - weiterhin synchronisieren

Der bisherige Response Letter ist gegenüber dem aktuellen Main-Source veraltet.

Besonders prüfen:

- „true physics“
- Summer infeasibility als physical deliverability failure
- L4/L5 decisions ≈ 0
- alte 81.2-%-Werte
- topology 4.7 % vs corrected 0.25 %
- physics-parameter term 4.4 %
- exact decomposition wording
- nonlinear exponential PWL/native status
- `decision regret` Definition
- shortfall topping-up vs valuation overlay.

Der Reviewer wird Response Letter und Manuskript nebeneinander lesen.

**Jede Abweichung ist auffälliger als ein isolierter Manuskriptfehler.**

---

# 9. AI-Disclosure / aktuelle Elsevier-Policy

Die letzte PDF enthält eine AI-Declaration, in der Claude Opus 5 für:

- language improvement,
- manuscript structuring,
- code generation,
- debugging

genannt wird.

Elsevier hat seine Journal-AI-Policy im August 2026 aktualisiert.

Relevant ist:

- AI use in writing/manuscript preparation soll als separate Declaration offengelegt werden.
- AI use im **research process / methods** soll bei Relevanz detailliert in der Methodik beschrieben werden.
- menschliche Verantwortung und Überprüfung bleiben zwingend.

## Problem

Wenn „code generation and debugging“ **Research Code** betrifft, ist eine reine Writing-Declaration möglicherweise zu wenig.

## Empfehlung

Klären:

### Falls AI nur Hilfscode / nicht wissenschaftlich relevante Skripte betroffen hat

Declaration präzisieren und Scope einschränken.

### Falls AI Code für Modellierung, Datenanalyse oder Solver-Auswertung erzeugt hat

Zusätzlich in Methods transparent beschreiben:

- Tool,
- Einsatzbereich,
- Human verification,
- Tests / cross-checks,
- keine autonome Interpretation.

Auch den offiziellen Section-Titel an die aktuelle Elsevier-Formulierung angleichen:

> Declaration of Generative AI and AI-assisted technologies in the writing process

---

# 10. Was muss noch simuliert werden?

## Zwingend / stark empfohlen als ein kombinierter kleiner Batch

### Vier Controls neu rechnen

- CP
- CP+L
- ND0
- L1

mit:

1. identischer Nicht-Faktor-Physics,
2. identischem Heating-Curve-/Return-T-/COP-Setup,
3. Solver Objective exakt aligned mit berichteter Economic Cost.

## Warum dieser eine Batch sehr wertvoll ist

Er schließt gleichzeitig:

- den verbleibenden Confound in der realen Fallstudie,
- die Objective-vs-Economic-Cost-Frage,
- die stärkste methodische Reviewer-Angriffsfläche.

---

## Nicht nötig vor dieser Revision

- alle 135 Synthetic Networks neu rechnen,
- distributed generation ergänzen,
- ring networks,
- full-year nonlinear solve,
- L4/L5 zwingend reoptimieren, sofern Claims reduziert werden,
- neue Messkampagne.

---

## Rechnen oder nur prüfen

### Nur Output/Code prüfen

- actual nonlinear weekly formulation,
- window dates / selection,
- delay floor vs round,
- authoritative 67.4/81.2 value,
- synthetic solver gaps,
- literature pump-share metric,
- CP+L loss-adder unit convention.

---

# 11. Priorisierte To-do-Liste

## P0 - vor Einreichung zwingend

- [ ] Memmingen-Decomposition entweder mit harmonisierten Controls neu rechnen oder nicht mehr als reines 2×2-Loss/Topology-Faktorial bezeichnen.
- [ ] Terminologie `decision regret` entscheiden/ggf. in `forward-valued schedule gap` umbenennen.
- [ ] Forward-Evaluator als Overlay oder energetisch geschlossene Fixed-Schedule-Evaluation formulieren.
- [ ] Results-„topping up“-Sprache an Methodik anpassen.
- [ ] `hydraulically/physically deliverable` auf tatsächlich geprüfte Constraints begrenzen.
- [ ] L4/L5-Reoptimisation-Claims überall entfernen.
- [ ] nonlinear weekly reference gegen tatsächlichen Code/Logs prüfen.
- [ ] 72-h-Windows exakt definieren.
- [ ] \(Q=\dot m c_p\Delta T\) korrigieren.
- [ ] CP+L-Loss-Adder-Einheiten korrigieren.
- [ ] Loss-number-Formel zeit- und einheitenkonsistent korrigieren.
- [ ] Delay `round` vs `floor` im aktuellen externen Input prüfen.
- [ ] 81.2-%-Altwert gegen authoritative output korrigieren.
- [ ] 0.01 / 0.1-% Solver-Gap konsistent darstellen.
- [ ] Vrain 2025 ergänzen.
- [ ] Cassetti 2025 ergänzen.
- [ ] Friedrich 2025 ergänzen.
- [ ] Bünning / Leitner / Giraud Claims gegen Volltexte prüfen.
- [ ] vollständigen finalen Source-Ordner kompilieren.
- [ ] Response Letter vollständig synchronisieren.
- [ ] AI Disclosure an aktuellen tatsächlichen Einsatzumfang anpassen.

---

## P1 - dringend empfohlen

- [ ] 33.8-%-MAPE nicht als uncertainty behandeln.
- [ ] Pump-energy Literaturvergleich dimensionsgleich machen.
- [ ] `design rule` → `screening heuristic`.
- [ ] `measured 15%` → `modelled 15.1% economic-cost gap`.
- [ ] `for most operators` eingrenzen.
- [ ] `standard planning setting` abschwächen.
- [ ] „does not depend on measurement-accurate schedule“ abschwächen.
- [ ] „never a copperplate“ entfernen.
- [ ] „incompetent controller“ entfernen.
- [ ] interne DRAFT/TODO-Kommentare vor Source-Upload löschen.
- [ ] Type-3-Fonts in Figures beheben.
- [ ] finaler cross-reference / metadata / title sync check.

---

# 12. Endgültige wissenschaftliche Einschätzung

## Was das Paper überzeugend zeigen kann

Nach den oben genannten Korrekturen ist die stärkste und am besten verteidigbare Aussage:

> In the tested centrally supplied radial networks, thermal-loss visibility explains nearly all of the economic difference between a loss-blind copperplate and a node-resolved dispatch representation, while spatial routing itself contributes little once non-network physics is held fixed.

Dazu kommt ein zweiter wertvoller Befund:

> A simplified model's own objective value is insufficient to assess the usefulness of its schedule; evaluating the fixed schedule under a common richer reference exposes loss shortfalls that the optimisation model itself cannot see.

Und ein dritter:

> Additional thermo-hydraulic detail beyond loss representation has limited impact on the forward-evaluated fixed schedule in the investigated industrial case, although this result is conditional on fixed capacities, hourly resolution, centrally located generation, and the prescribed temperature regime.

Das ist **ein solides Applied-Energy-Paper**.

## Was das Paper derzeit noch nicht sauber zeigen kann

Noch nicht belastbar sind Aussagen wie:

- „exact loss/topology decomposition“ für die as-run Memmingen-Controls ohne Zusatzqualifikation,
- „decision regret“ im klassischen mathematischen Sinn,
- vollständige physical deliverability der Schedules,
- station-level hydraulics do not change dispatch decisions,
- universal model-selection rule,
- „most operators“,
- generelle Irrelevanz von thermo-hydraulic detail,
- ein vollständig native nonlinear annual/weekly reference, solange die exponential-PWL-Frage nicht geklärt ist.

---

# 13. Finales Go/No-Go

## Heute: **NO-GO**

Aber die verbleibenden Probleme sind jetzt **klar begrenzt**.

Ich sehe keinen Bedarf für eine erneute komplette Forschungsstudie.

Der zentrale verbleibende Rechenblock kann sinnvoll zu **einem einzigen kleinen Vier-Control-Sensitivity-Batch** zusammengefasst werden.

Danach braucht es vor allem:

- terminologische Präzision,
- Synchronisierung,
- Literaturaktualisierung,
- Gleichungs-/Unit-Fixes,
- finalen Source/PDF-Preflight.

Wenn diese Punkte geschlossen sind, würde ich die Arbeit **für eine erneute Einreichung bei Applied Energy befürworten**.

---

# 14. Extern geprüfte aktuelle Literatur / Policy

## Vrain et al. (2025)
*An aggregation method to model district heating networks in large-scale multi-energy simulations.*  
Energy 334, 137384.  
DOI: **10.1016/j.energy.2025.137384**

## Cassetti et al. (2025)
*Impact of spatial resolution in modelling decarbonized district heating networks.*  
Energy 334, 137357.  
DOI: **10.1016/j.energy.2025.137357**

## Friedrich et al. (2025)
*Optimizing district heating operations: Network modeling and its implications on system efficiency and operation.*  
Smart Energy 18, 100175.  
DOI: **10.1016/j.segy.2025.100175**

## Elsevier generative-AI policy
Elsevier updated its journal guidance in August 2026. The key practical implication for this manuscript is that AI use in manuscript preparation should be disclosed, while relevant AI use in the research process/methodology should be described in sufficient methodological detail rather than only in the writing declaration.

---

**Audit completed against the latest available wrapper source plus the latest compiled manuscript and correction history. A final definitive submission audit requires the complete current LaTeX source tree, because several core sections are included from external files not present in the latest upload.**
