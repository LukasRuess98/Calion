# Vollständige Review- und Überarbeitungsliste für das AgNes-Paper
## *Booked Capacity Instead of Peak Load – Effects of the AgNes grid-charge reform on electrifying industrial process heat*

**Ziel dieser Liste:** vollständige Durchsicht des aktuellen Manuskripts mit Fokus auf methodische Konsistenz, Ergebnisinterpretation, mathematische Sauberkeit, Nachvollziehbarkeit und Journal-Tauglichkeit.

Die Liste ist bewusst **nicht nur auf eine methodische Neuentwicklung ausgerichtet**. Für jeden Punkt wird unterschieden zwischen:

- **Minimaländerung:** Was im bestehenden Studiendesign zwingend oder sinnvoll angepasst werden sollte, ohne die Methode grundsätzlich umzubauen.
- **Stärkere Erweiterung:** Was zusätzlich gemacht werden könnte, falls das Paper methodisch weiter aufgewertet werden soll.

**Prioritäten**
- 🔴 **zwingend vor Einreichung**
- 🟠 **stark empfohlen**
- 🟡 **sinnvolle Verbesserung**
- 🟢 **Stärke – beibehalten / stärker herausarbeiten**

---

# A. Übergeordnete Bewertung

## A1. 🟢 Analytische Bestellregel ist der stärkste methodische Beitrag

### Stärke
Das Paper leitet eine geschlossene Regel für die kostenoptimale Bestellkapazität bei gegebenem Lastgang her und verknüpft diese mit einer Lastdauerlinie.

### Beibehalten
- analytische Herleitung,
- kritische Überschreitungsdauer,
- grafische Interpretation über Jahresdauerlinie,
- Vergleich analytische Regel vs. LP.

### Stärker herausarbeiten
Die eigentliche wissenschaftliche Stärke ist nicht nur:
> „Wir bestimmen eine optimale Bestellkapazität.“

Sondern:
> **Die Regel ist für einen gegebenen Lastgang exakt; Abweichungen entstehen erst, wenn der Lastgang selbst durch die gekoppelte Elektrifizierung endogen wird.**

---

## A2. 🟢 Kopplung von Tarif und Anlagenauslegung ist stark

### Stärke
Das Modell koppelt:
- Grundlast,
- Wärmepumpe,
- Elektrodenkessel,
- Gaskessel,
- Wärmespeicher,
- Netzentgelt,
- Beschaffungsform.

Das ist wesentlich stärker als eine reine Tarifkostenrechnung.

### Empfehlung
Diese Kopplung deutlicher als methodischen Beitrag formulieren.

---

## A3. 🟢 Reale Fabriklastgänge sind wertvoll

### Stärke
Vier reale industrielle Fälle mit stark unterschiedlichen Größen und Laststrukturen zeigen, dass die Wirkung nicht trivial ist.

### Einschränkung
Die Fälle sind **Demonstrationsfälle**, keine statistische Stichprobe.

### Minimaländerung
Im gesamten Paper konsequent:
- „case studies“
- „investigated sites“
- nicht „industrial consumers in general“.

---

# B. Titel, Abstract, Keywords, Highlights

## B1. 🟡 Titel etwas stärker auf methodischen Kern ausrichten

### Aktuell
Der Titel fokussiert stark auf AgNes und Elektrifizierung.

### Problem
Der analytische Beitrag ist im Titel kaum sichtbar.

### Minimaländerung
Titel kann bestehen bleiben.

### Stärkere Variante
Beispielsweise:
> **Booked Capacity Instead of Peak Load: Analytical Booking Rules and Endogenous Electrification under AgNes**

oder:
> **Capacity Subscription under Industrial Electrification: Analytical Booking Rules and AgNes Case Studies**

---

## B2. 🔴 Abstract: klarstellen, worauf sich 30,7–58,5 EUR/MWh beziehen

### Problem
Die Spannweite ist aus der zentralen Ergebnistabelle nicht unmittelbar nachvollziehbar.

### Minimaländerung
Im Abstract ergänzen:
> „across all sites and tariff–procurement combinations“

### Zusätzlich
Falls es inkrementelle Kosten sind, ausdrücklich:
> „incremental levelized cost of process heat“

---

## B3. 🟠 Abstract: 34,7 % besser interpretieren

### Aktuell sinngemäß
Die analytische Regel weicht im gekoppelten Modell um bis zu 34,7 % ab.

### Problem
Das klingt, als sei die Regel ungenau.

### Besser
> The analytical rule remains exact conditional on a given load-duration curve but differs by up to 34.7% from the coupled optimum because electrification endogenously reshapes that curve.

---

## B4. 🟡 Abstract: Interaktionsergebnis präziser formulieren

### Aktuell
„site-specific heterogeneous interaction“.

### Verbesserung
Nicht nur „uneinheitlich“, sondern:
> „the interaction changes sign across sites“

Das ist informativer.

---

## B5. 🟡 Keywords vereinheitlichen

Prüfen:
- „capacity subscription“
- „booked capacity“
- „grid tariff“
- „network tariff“
- „grid charge“

Nicht mehrere nahezu synonyme Begriffe ohne Definition parallel verwenden.

---

# C. Einleitung und Forschungslücke

## C1. 🟠 Forschungslücke stärker zuspitzen

### Aktuell
Mehrere Literaturstränge werden genannt.

### Problem
Die genaue Novelty ist noch nicht maximal scharf.

### Minimaländerung
Explizit drei Lücken trennen:

1. **Closed-form booking condition** under AgNes.
2. **Endogenous load reshaping** through industrial electrification.
3. **Interaction with market-based flexibility** under Day-Ahead procurement.

---

## C2. 🟠 Nicht behaupten, Bestellkapazität sei als Optimierungsvariable generell neu

### Problem
Capacity-subscription-Tarife und optimierte subscribed capacity sind international bereits untersucht worden.

### Minimaländerung
Novelty enger formulieren:
> AgNes-specific analytical booking condition and coupling with industrial process-heat electrification.

---

## C3. 🟡 Beitrag und Hypothesen klarer strukturieren

### Empfehlung
Am Ende der Einleitung drei Forschungsfragen:

**RQ1:** How can cost-minimal booked capacity be derived analytically for a fixed load profile?

**RQ2:** How does endogenous industrial electrification alter the optimal booked capacity?

**RQ3:** How does the interaction between tariff regime and electricity procurement affect electrification economics?

---

## C4. 🟡 Break-even als vierter Beitrag nur behalten, wenn methodisch sauber

Wenn Break-even lediglich mit fixiertem ELEC-Design berechnet wird, nicht als gleichwertigen Hauptbeitrag ankündigen.

---

# D. Regulatorische Abbildung von AgNes und StromNEV

## D1. 🔴 „unverified“ in Tabelle 1 muss raus

### Problem
Interne QA-Markierungen wie:
- reviewed,
- unverified,
- derived

gehören nicht in die Journalversion.

### Minimaländerung
- verifizieren,
- oder als explizite Szenarioannahme deklarieren.

---

## D2. 🔴 Finalen regulatorischen Status unmittelbar vor Einreichung aktualisieren

### Problem
AgNes ist zum Manuskriptzeitpunkt Entwurf.

### Minimaländerung
Kurz vor Submission prüfen:
- aktueller BNetzA-Stand,
- Konsultationsstatus,
- Inkrafttreten,
- Änderungen gegenüber 06.08.2026.

---

## D3. 🟠 Szenarioannahmen vs. regulatorische Vorgaben strikt trennen

### Problem
Einige Modellparameter werden aus Entwurf, Preisblättern oder eigenen Annahmen kombiniert.

### Minimaländerung
Tabelle mit drei Spalten:
- regulatory requirement,
- modelling assumption,
- source.

---

## D4. 🔴 StromNEV-Baseline nicht als „nur regimekonsistent“ stehen lassen

### Problem
Der Vergleich zu AgNes wird quantitativ interpretiert.

### Minimaländerung
Genau erklären:
- wie die Tarifpaare ausgewählt werden,
- wann ein Lauf als konsistent gilt,
- wie Mehrdeutigkeit behandelt wird.

### Stärkere Lösung
Exakte Enumeration der Tarifregime.

---

## D5. 🔴 Wenn StromNEV nicht exakt ist: Unsicherheit quantifizieren

Falls exakte Modellierung nicht umgesetzt wird:

### Minimaländerung
Mindestens:
- Abweichung der Approximation zu einer exakten Nachrechnung für alle vier Standorte,
- oder ex-post reconstruction der StromNEV-Kosten.

### Ziel
Nachweisen, dass die Approximation die berichteten AgNes-Differenzen nicht dominiert.

---

## D6. 🔴 Tarifstruktur- vs. Tarifniveau-Effekt trennen

### Problem
AgNes und StromNEV können unterschiedliche absolute Erlösniveaus haben.

### Minimaländerung
Im Text explizit sagen:
> The reported differences combine tariff-structure and tariff-level effects.

### Stärkere Erweiterung
Revenue-neutral calibration.

---

## D7. 🟠 Revenue-neutral comparison ergänzen, falls möglich

### Ziel
\[
R_{\mathrm{AgNes}}^{ref}=R_{\mathrm{StromNEV}}^{ref}
\]

### Vorteil
Isoliert den Mechanismuseffekt.

---

## D8. 🟡 Preisblattwahl begründen

Warum genau:
- Stadtwerke Tübingen,
- EAM,
- Bayernwerk?

### Minimaländerung
Auswahlkriterium nennen:
- Netzebene,
- Datenverfügbarkeit,
- Größenordnung,
- regionale Repräsentation.

---

## D9. 🟡 Sondernetzentgelte sauber abgrenzen

Ausgeschlossen sind:
- §19 StromNEV,
- Baukostenzuschüsse,
- zeitvariable Netzentgelte.

### Minimaländerung
Klar sagen:
> The analysis isolates the standard tariff mechanism.

---

# E. Analytische Herleitung

## E1. 🔴 Einheiten in \(E_2(C)\) korrigieren

Sauber:

\[
E_2(C)=\frac{\Delta t}{1000}\sum_t \max(P_t-C,0)
\]

bei \(P\) in kW und \(E\) in MWh.

---

## E2. 🔴 Alle Symbole vollständig definieren

Mindestens:
- \(P_t\),
- \(C\),
- \(E_1\),
- \(E_2\),
- \(D(C)\),
- \(KP\),
- \(AP_1\),
- \(AP_2\),
- \(h^*\),
- \(\beta\),
- \(P_{\mathrm{grid}}\).

---

## E3. 🔴 Bestellregel mit Constraints formulieren

Nicht nur:

\[
C^*=PLDC(h^*)
\]

sondern:

\[
C^*=
\operatorname{clip}
\left(
PLDC(h^*),C_{\min},C_{\max}
\right)
\]

---

## E4. 🟠 Diskrete Lastdauerlinie mathematisch korrekt behandeln

### Problem
Bei diskreten Daten ist \(D(C)=h^*\) nicht immer exakt lösbar.

### Besser
\[
D(C^{*+})\le h^* \le D(C^{*-})
\]

---

## E5. 🟠 Eindeutigkeit des Optimums diskutieren

Bei Plateaus der Lastdauerlinie können mehrere \(C\)-Werte gleiche Kosten erzeugen.

### Minimaländerung
Ein Satz:
> For discrete profiles, multiple adjacent breakpoints may be cost-equivalent.

---

## E6. 🟡 Dimensionslose Kennzahl \(\theta\) klarer definieren

### Problem
Bedeutung und Interpretation sind aktuell zu wenig intuitiv.

### Minimaländerung
Explizit:
- was numerator/denominator physikalisch bedeuten,
- warum \(\theta=1\) ein sinnvoller Referenzpunkt ist.

---

## E7. 🔴 \(\theta\)-Resultat auf Datenfehler prüfen

### Problem
Berichtete 2-%-Aussage passt nicht zur Schlussfolgerung.

### Maßnahme
Originalauswertung prüfen.

---

## E8. 🟠 „\(\theta \approx 1\) ist Grenze“ nur bei belastbarer Evidenz schreiben

Falls kein klarer Sprung vorliegt:
> \(\theta\) is associated with a shift toward partial booking

statt:
> \(\theta=1\) marks the boundary.

---

## E9. 🟡 Abschnitt 3.5 „Prüfbare Hypothesen zum Speicherwert“ präzisieren

### Problem
Der aktuelle Text ist mathematisch/inhaltlich zu knapp.

### Minimaländerung
Hypothesen explizit nummerieren:

- H1: Storage value remains high if storage lowers subscribed capacity.
- H2: Storage value falls if it only avoids short AP2 exceedances.
- H3: Market arbitrage can restore storage value under dynamic prices.

---

# F. Modellformulierung

## F1. 🟠 Vollständige Gleichungen ins Manuskript oder Supplement

Aktuell sind Teile der Modellbeschreibung zu prose-lastig.

### Mindestens dokumentieren
- Strombilanz,
- Wärmebilanz,
- HP,
- EK,
- Gas,
- TES,
- Kapazitätsgrenzen,
- Netzimport,
- AgNes split,
- StromNEV-Kosten,
- Investitionskosten,
- O&M,
- cyclic storage.

---

## F2. 🔴 „LP-exakt“ mathematisch oder empirisch belegen

### Problem
Insbesondere bei negativen Strompreisen können künstliche Kreisläufe entstehen.

### Minimaländerung
Prüfen:
\[
\sum_t \min(q_t^{ch},q_t^{dis})=0
\]

### Falls nicht null
Modell anpassen.

---

## F3. 🟠 Negative Strompreise explizit behandeln

Fragen:
- Können HP/TES bei negativen Preisen künstlich überladen?
- Gibt es Spill/curtailment?
- Gibt es simultanes Laden/Entladen?
- Ist Heat dumping ausgeschlossen?

### Minimaländerung
Explizite Aussage.

---

## F4. 🟡 Perfect Foresight klar als Optimierungsbenchmark kennzeichnen

Nicht nur in Limitations erwähnen.

### Besser
Schon in Methodik:
> All optimization runs represent an oracle benchmark with perfect foresight over the annual horizon.

---

## F5. 🔴 Ex-ante-Entscheidungsstruktur transparent machen

Welche Variablen sind:
- vor Jahresbeginn fix,
- operativ,
- nachträglich?

### Minimaländerung
Tabelle:
| Variable | Stage | Information available |
|---|---|---|

---

## F6. 🟠 Netzanschlussgrenze \(P_{\mathrm{grid}}\) begründen

### Problem
Fixe Grenze kann Ergebnis stark beeinflussen.

### Minimaländerung
- Herleitung,
- Quelle,
- Sensitivität falls relevant.

---

## F7. 🟡 Spannungsebene als fixierte Annahme klar abgrenzen

### Formulierung
> Results are conditional on the existing connection level.

---

## F8. 🟠 Wärmeband-Modell besser erklären

### Problem
Ein generisches Band + \(\kappa\) wirkt ohne Zusatzinformation abstrakt.

### Minimaländerung
Je Standort:
- Anteil HP-fähig,
- Anteil nur über EK/Gas,
- COP,
- Begründung.

---

## F9. 🟡 ±10 Prozentpunkte für Bandanteile begründen

Warum 10?
- Messunsicherheit?
- Literatur?
- pragmatischer Bereich?

---

## F10. 🟠 COP-Annahmen deutlich sichtbar machen

Für Wärmepumpen sind COPs entscheidend.

### Minimaländerung
Technologieparameter-Tabelle im Haupttext oder Supplement.

---

## F11. 🟠 Elektrodenkesselparameter transparent machen

Da EK immer 0 ist, muss nachvollziehbar sein:
- CAPEX,
- Wirkungsgrad,
- OPEX,
- Temperaturrestriktion.

---

## F12. 🟡 Gaskesselwirkungsgrad konsistent verwenden

Prüfen:
- Nutzwärme vs. Brennstoff,
- Gaspreis auf Hu/Hs,
- CO₂-Faktor auf Brennstoffenergie.

---

## F13. 🟠 Speicherparameter vollständig dokumentieren

Mindestens:
- CAPEX,
- Lade-/Entladeleistung,
- Verluste,
- Wirkungsgrad,
- cyclic condition,
- maximale Energie,
- Lebensdauer.

---

## F14. 🟡 Keine Zeitreihenaggregation korrekt benennen

Besser:
> no representative-period clustering

statt pauschal:
> time series are not aggregated.

---

# G. Daten

## G1. 🟠 Standortdaten stärker charakterisieren

Zusätzlich zu:
- Jahreswärme,
- Peak,
- Full-load hours,
- Grundlast,

sinnvoll:
- Load factor,
- Peak-to-average ratio,
- \(P_{\mathrm{heat,peak}}/P_{\mathrm{base,max}}\),
- ggf. Variationskoeffizient.

---

## G2. 🟠 Unterschiedliche Datenjahre transparent behandeln

### Minimaländerung
Je Standort:
- Lastjahr,
- DA-Preisjahr,
- Netzentgeltjahr.

---

## G3. 🔴 Day-Ahead-Preis-Matching eindeutig dokumentieren

### Unbedingt beantworten
- 2023-Profil mit 2023-Preis?
- 2024-Profil mit 2024-Preis?
- einheitliches Preisjahr?

---

## G4. 🟡 Zeitumstellung dokumentieren

Bei Jahreszeitreihen:
- CET/CEST,
- 23-/25-Stunden-Tage,
- Leap day.

---

## G5. 🟠 15-min-Fälle begründen

Warum Chemie und Papier?

### Minimaländerung
Ein Satz mit Auswahlkriterium.

---

## G6. 🟡 Datenvertraulichkeit sauber erklären

Da Lastreihen nicht veröffentlicht werden können:
- welche aggregierten Daten werden bereitgestellt?
- können synthetisierte Profile reproduziert werden?
- welche Modellinputs sind auf Zenodo?

---

# H. Fixpreis vs. Day-Ahead

## H1. 🔴 Preisniveau-Neutralität prüfen

### Problem
Sonst misst DA vs. Fixpreis nicht nur Flexibilität.

### Minimaländerung
Im Text offenlegen:
- durchschnittlicher Fixpreis,
- durchschnittlicher DA-Preis,
- lastgewichteter DA-Preis.

---

## H2. 🟠 Fixpreis möglichst aus DA-Mittel ableiten

\[
p_\mathrm{fix}=\frac{1}{T}\sum_t p_t^{DA}
\]

### Ziel
Zeitstruktur statt Preisniveau vergleichen.

---

## H3. 🟠 Falls nicht neutralisiert: Ergebnis anders benennen

Nicht:
> value of flexibility

sondern:
> combined effect of dynamic price level and temporal variation.

---

## H4. 🟡 15-min-DA-Preise bzw. replizierte Stundenpreise sauber kennzeichnen

### Minimaländerung
Klar:
> Hourly DA prices were repeated within each 15-min interval.

---

## H5. 🟡 Intraday nicht als Bestandteil der Analyse erscheinen lassen

Explizit:
- only Day-Ahead,
- no intraday,
- no balancing.

---

# I. Ergebnisdarstellung – allgemeine Struktur

## I1. 🟠 Results stärker entlang der Forschungsfragen strukturieren

Empfohlen:

1. Analytical rule validation  
2. Endogenous booking gap  
3. Tariff effects  
4. Market interaction  
5. Technology design  
6. Robustness / sensitivity  
7. Break-even  

---

## I2. 🟢 Exogen → gekoppelt → realisiert als zentrale Story

Diese Reihenfolge unbedingt beibehalten und stärker visualisieren.

---

## I3. 🟠 Nicht zu viele Ergebnisdimensionen in einem Absatz mischen

Aktuell stehen in einem kurzen Results-Abschnitt:
- LCOH,
- interaction,
- HP,
- TES,
- EK,
- system value.

### Minimaländerung
In Unterabschnitte trennen.

---

# J. Ergebnis: 15-min-Validierung

## J1. 🔴 Nicht nur LCOH vergleichen

Zusätzlich berichten:

\[
\Delta C^*
\]

\[
\Delta P_{\max}
\]

\[
\Delta E_2
\]

\[
\Delta(E_2/E)
\]

\[
\Delta E_{\mathrm{TES}}
\]

\[
\Delta P_{\mathrm{HP}}
\]

---

## J2. 🟡 Begriff „validation“ ersetzen

Besser:
- temporal-resolution robustness,
- temporal-resolution sensitivity.

---

# K. Ergebnis: Regimewechsel

## K1. 🟢 Spannweite der LCOH-Wirkung ist stark

Beibehalten:
- negative und positive Effekte,
- keine künstliche Harmonisierung.

---

## K2. 🟠 Vorzeichen standortspezifisch erklären

Für jeden Standort kurz:
- Warum profitiert er?
- Warum nicht?

Nicht nur Werte berichten.

---

## K3. 🟠 Relative und absolute Effekte gemeinsam zeigen

Neben EUR/MWh:
\[
\frac{\Delta LCOH}{LCOH_{\mathrm{ref}}}
\]

---

# L. Ergebnis: Interaktion Netzregime × Beschaffungsform

## L1. 🟢 2×2-Interaktion ist methodisch sinnvoll

Beibehalten.

---

## L2. 🟠 Interaction term mathematisch definieren

Beispielsweise:

\[
\Delta_{\mathrm{inter}}
=
(K_{A,D}-K_{A,F})-
(K_{S,D}-K_{S,F})
\]

mit sauberer Zeichendefinition.

---

## L3. 🟠 Interpretation des Vorzeichens definieren

Was bedeutet:
- \(\Delta_{\mathrm{inter}}>0\)?
- \(\Delta_{\mathrm{inter}}<0\)?

---

## L4. 🟠 Nicht bei „uneinheitlich“ stehen bleiben

Mechanistisch erklären über:
- \(C/P_{\max}\),
- \(E_2/E\),
- Load factor,
- storage,
- heat/electric ratio.

---

## L5. 🟢 Metallfall als Kontrastfall nutzen

Der Metallfall hat offenbar eine deutlich andere Bestell-/Überschreitungsstruktur.

### Empfehlung
Als expliziten Mechanism Case hervorheben.

---

# M. Ergebnis: Anlagenauslegung

## M1. 🟠 Absolute Kapazitätsänderungen normalisieren

Zusätzlich:
\[
\Delta P_{\mathrm{HP}}/P_{\mathrm{HP,ref}}
\]

\[
\Delta E_{\mathrm{TES}}/E_{\mathrm{TES,ref}}
\]

---

## M2. 🟡 Größeneffekt zwischen Standorten berücksichtigen

Bei 254 MWh vs. 232,767 MWh Jahreswärme sind absolute kW/kWh-Vergleiche allein wenig aussagekräftig.

---

## M3. 🟠 Elektrodenkessel 0 kW erklären

Mögliche Erklärung:
- HP wirtschaftlich überlegen,
- Gas als Peak-/HT-Technologie günstiger,
- EK-CAPEX/Preisstruktur,
- Temperaturannahmen.

---

## M4. 🟡 Falls EK nicht relevant ist: kommunikativ zurückstufen

Nicht im Abstract als zentrale Technologie darstellen, wenn er nie gewählt wird.

---

# N. Ergebnis: Speicher

## N1. 🔴 Aggregierten „Systemwert 361,848 EUR/a“ über Szenarien nicht so stehen lassen

### Problem
Gegenseitig ausschließende Szenarien werden aufsummiert.

### Minimaländerung
Ersetzen durch:
- Range,
- Median,
- site-specific values.

---

## N2. 🟠 Speicherwert normalisieren

Berichten:
- EUR/MWh_th,
- % Kostenreduktion,
- EUR/kWh_TES,
- ggf. CAPEX-relative Einsparung.

---

## N3. 🟠 Speichermechanismus erklären

Unterscheiden:
- Senkung der Bestellkapazität,
- Verringerung AP2,
- Marktpreisverschiebung,
- Wärmeverschiebung.

---

## N4. 🟡 Speicher nicht nur als Peak-Shaving-Technologie interpretieren

Stärker systemisch:
> cost-minimizing temporal flexibility.

---

# O. Ergebnis: analytische Regel und 34,7-%-Gap

## O1. 🟢 Wichtigstes Ergebnis stärker visualisieren

### Empfohlene Abbildung
x:
\[
C_{\mathrm{analytical}}
\]

y:
\[
C_{\mathrm{coupled}}
\]

mit 45°-Linie.

---

## O2. 🟠 „Fehler der Regel“ vermeiden

Besser:
> deviation from the exogenous-profile prediction

statt:
> rule error.

---

## O3. 🟠 Begriff Endogeneity Gap einführen

\[
G_C=
\frac{C_{\mathrm{coupled}}-C_{\mathrm{exogenous}}}
{C_{\mathrm{coupled}}}
\]

---

## O4. 🟠 Ursache quantitativ untersuchen

Mindestens korrelativ:
- Load factor,
- storage size,
- heat share,
- \(E_2/E\).

Auch bei vier Fällen nur deskriptiv, nicht statistisch überinterpretieren.

---

# P. Ergebnis: \(\theta\)

## P1. 🔴 Zahlen prüfen

Der 2-%-/98-%-Sachverhalt muss geklärt werden.

---

## P2. 🟠 Regimegrenze nicht überinterpretieren

Wenn die Evidenz schwach:
> indicative transition

statt:
> boundary.

---

## P3. 🟡 \(\theta\)-Abbildung ergänzen

x:
\[
\theta
\]

y:
\[
C/P_{\max}
\]

---

# Q. Ergebnis: Break-even

## Q1. 🔴 Begriff „Break-even“ präzisieren

Wenn Design fix:
> conditional break-even.

---

## Q2. 🟠 Falls möglich, vollständige Reoptimierung

Für jeden Preis neues Optimum.

---

## Q3. 🔴 CO₂-Break-even nicht aus nur 2/8 Fällen generalisieren

### Minimaländerung
Zensierte Darstellung:
- \(>x\),
- \(<x\),
- no crossing in range.

---

## Q4. 🟡 Gaspreis-Break-even als stärkeres Ergebnis priorisieren

7/8 Fälle sind deutlich robuster.

---

## Q5. 🟡 Preisintervall begründen

Warum genau dieser Suchbereich?

---

# R. Diskussion

## R1. 🟠 Discussion stärker von Results trennen

Nicht nur Resultate wiederholen.

### Discussion sollte beantworten:
- Was bedeutet das für Tarifdesign?
- Was bedeutet es für industrielle Elektrifizierung?
- Wann reicht eine einfache Bestellregel?
- Wann ist gekoppelte Optimierung nötig?

---

## R2. 🟢 Standortheterogenität als Policy-Befund formulieren

Nicht:
> results are inconsistent.

Sondern:
> tariff incidence depends on load shape and the chosen balance between subscription and exceedance.

---

## R3. 🟠 Nicht behaupten, Speicher sei generell weniger wertvoll

Nur für untersuchte Parameter und Standorte.

---

## R4. 🟠 „Elektrifizierung selbst“ präzisieren

Besser:
> endogenous reshaping of electrical demand under electrification.

---

## R5. 🟡 Vergleich mit internationaler Capacity-Tariff-Literatur verstärken

Diskussion nicht nur auf AgNes beschränken.

---

## R6. 🟡 Policy-Relevanz der ex-ante-Bestellung hervorheben

Die Unsicherheit ist kein Nebenthema, sondern integraler Bestandteil des Mechanismus.

---

# S. Limitationen

## S1. 🟢 Perfect Foresight als Limitation beibehalten

Aber prominenter.

---

## S2. 🟠 Nur vier Standorte klar als Limitation

Nicht statistisch generalisieren.

---

## S3. 🟠 Unterschiedliche Jahre als Limitation

Aber innerhalb-site comparisons bleiben valide.

---

## S4. 🟠 Fixierte Netzebene als Limitation

---

## S5. 🟡 Keine Baukostenzuschüsse

---

## S6. 🟡 Keine Sondernetzentgelte

---

## S7. 🟡 Keine dynamische Anpassung der gebuchten Kapazität

---

## S8. 🟡 Keine Intraday-/Balancing-Märkte

---

## S9. 🟡 Temperaturbandvereinfachung

---

## S10. 🟡 Keine Investitionsunsicherheit

CAPEX, COP, Brennstoffpreise deterministisch.

---

# T. Praktische Anwendung / 5-Schritte-Verfahren

## T1. 🟠 Speicher nicht erst vollständig nach Bestellkapazität betrachten

### Problem
Speicher verändert Lastdauerlinie.

### Minimaländerung
Schritt 5 umformulieren:
> If storage or electrification materially reshapes the load profile, iterate the booking calculation or solve the coupled model.

---

## T2. 🟠 Screening-Logik explizit machen

Die analytische Regel ist:
- sehr gut für initial screening,
- nicht immer finale Entscheidung.

---

## T3. 🟡 Schwellenwert für „gekoppelte Optimierung nötig“ ableiten

Falls möglich aus den Fällen:
- z. B. hoher heat/base-load ratio,
- hoher storage flexibility,
- hoher Endogeneity Gap.

---

# U. Fazit

## U1. 🟠 Fazit stärker auf methodischen Beitrag konzentrieren

Weniger:
- einzelne numerische Ergebnisse.

Mehr:
- analytische Regel,
- Grenze der Exogenitätsannahme,
- Standortabhängigkeit.

---

## U2. 🟠 Nicht „Regel funktioniert gut“ ohne Kondition

Besser:
> The rule is exact conditional on a known load-duration curve.

---

## U3. 🟡 Policy-Aussage nicht über vier Fälle hinausziehen

Keine allgemeine Behauptung:
> AgNes makes electrification cheaper.

Sondern:
> AgNes can either increase or decrease incremental electrification costs depending on site characteristics.

---

# V. Tabellen

## V1. 🟠 Technologieparameter-Tabelle ergänzen

Mindestens:
- CAPEX,
- lifetime,
- WACC/discount rate,
- fixed O&M,
- HP COP,
- EK efficiency,
- gas boiler efficiency,
- TES efficiency/losses,
- storage CAPEX.

---

## V2. 🟠 Preisannahmen-Tabelle ergänzen

- gas,
- CO₂,
- fix electricity,
- DA year,
- network charges.

---

## V3. 🟠 Regulatorische Tabelle bereinigen

Keine internen QA-Status.

---

## V4. 🟡 KPI-Tabelle erweitern

Je Standort:
- LCOH,
- \(C/P_{\max}\),
- \(E_2/E\),
- Endogeneity Gap,
- HP,
- TES,
- interaction term.

---

# W. Abbildungen

## W1. 🟢 Systemgrenze beibehalten

---

## W2. 🟠 Jahresdauerlinien größer und lesbarer

Aktuell sind vier kleine Panels schwer lesbar.

### Verbesserung
- größere Schrift,
- \(C^*\) klar markieren,
- \(h^*\) klar markieren,
- AP2-Fläche erklären.

---

## W3. 🟠 Neue Kernabbildung „analytical vs. coupled booking“

Sehr empfehlenswert.

---

## W4. 🟡 Break-even-Abbildung nur behalten, wenn Methodik präzisiert

---

## W5. 🟡 Anlagenstack normalisieren oder ergänzen

Absolute MW plus relative Shares.

---

# X. Terminologie

## X1. 🟠 Einheitliche Begriffe verwenden

Empfehlung:
- **booked capacity** für \(C\),
- **capacity subscription** für Mechanismus,
- **capacity exceedance** für \(P>C\),
- **exceedance energy** für \(E_2\).

---

## X2. 🟡 „grid fee“ vs. „network tariff“

Für Journaltext besser überwiegend:
> network tariff / network charge

---

## X3. 🟡 „peak load“ sauber unterscheiden

- annual peak demand,
- grid import peak,
- heat peak,
- booked capacity.

---

# Y. Statistik und Generalisierbarkeit

## Y1. 🔴 Keine statistischen Generalisierungen aus n=4

Keine Begriffe wie:
- representative,
- robust across industry,
- general industrial effect.

---

## Y2. 🟠 Wenn keine größere Stichprobe geplant ist: Fallauswahl stärker begründen

Warum diese vier?
- Branchenkontrast,
- Größenkontrast,
- Load-shape contrast.

---

## Y3. 🟡 Optional: parametrische Mechanism Study

Nicht zwingend für bestehendes Paper, aber hoher Mehrwert.

Dimensionen:
- load factor,
- peakiness,
- heat/base ratio,
- tariff ratio,
- storage flexibility.

---

# Z. Reproduzierbarkeit

## Z1. 🟢 Zenodo unbedingt beibehalten

---

## Z2. 🟠 Versionierung fixieren

Manuskript sollte konkrete Version referenzieren.

---

## Z3. 🟠 README mit reproduzierbarem Workflow

- environment,
- solver,
- run sequence,
- configs,
- post-processing.

---

## Z4. 🟡 Vertrauliche Lastprofile ersetzen

Optional:
- anonymisierte Kennwerte,
- synthetische Demo-Profile.

---

# AA. Konkrete minimale Änderungen ohne Methodenumbau

Wenn die Methode **nicht grundlegend erweitert** werden soll, würde ich mindestens Folgendes umsetzen:

1. Alle Gleichungen korrigieren und vollständig definieren.
2. \(\theta\)-Inkonsistenz prüfen.
3. „unverified“-Markierungen entfernen.
4. StromNEV-Abbildung wesentlich genauer erklären.
5. Falls StromNEV nicht exakt ist, Approximation quantifizieren.
6. Perfect Foresight als Oracle Benchmark kennzeichnen.
7. Ex-ante-Interpretation entsprechend vorsichtiger formulieren.
8. 34,7 % als Endogenitäts- statt Regelproblem interpretieren.
9. praktische 5-Schritte-Regel um Iterationshinweis ergänzen.
10. Stunden-/15-min-Vergleich um \(C^*\), \(E_2\), Peak ergänzen.
11. Fixpreis-/DA-Preisniveau offenlegen.
12. Interaction term mathematisch definieren.
13. Speicherwert nicht über Szenarien aufsummieren.
14. Break-even korrekt als conditional break-even benennen.
15. CO₂-Break-even als zensierte Schwelle berichten.
16. absolute Kapazitätsänderungen normalisieren.
17. Elektrodenkessel-Nullergebnis erklären.
18. Temperaturbandannahmen transparenter machen.
19. Netzebene als konditionale Annahme formulieren.
20. LCOH konsequent als „incremental“ bezeichnen.
21. Auswahl der 15-min-Fälle begründen.
22. Datenjahre und DA-Matching offenlegen.
23. Resultate stärker nach Forschungsfragen strukturieren.
24. Discussion stärker mechanistisch schreiben.
25. Conclusion weniger generalisieren.
26. Technologieparameter-Tabelle ergänzen.
27. Preisannahmen-Tabelle ergänzen.
28. Terminologie vereinheitlichen.
29. Figuren lesbarer machen.
30. Abstract an tatsächliche Methodik/Interpretation anpassen.

---

# AB. Stärkere Erweiterungen, falls ein höheres methodisches Niveau angestrebt wird

Diese Punkte sind **nicht zwingend**, wenn das Studiendesign bewusst kompakt bleiben soll.

## AB1. Forecast-/Ex-ante-Unsicherheit
- Oracle vs. forecast booking
- Regret

## AB2. Revenue-neutral tariff comparison
- Struktur- vs. Preisniveau-Effekt

## AB3. Vollständige Reoptimierung der Break-even-Analyse

## AB4. Parametrische Mechanism Study

## AB5. 15-min-Kernmodell für alle Fälle

## AB6. Endogeneity-Gap-Karte / Typologie

---

# AC. Empfohlene neue Kernbotschaft

Die wissenschaftlich stärkste Story des aktuellen Manuskripts ist:

> **For a fixed load profile, the cost-minimal booked capacity can be derived analytically from the load-duration curve. The rule remains exact conditional on the realised curve. Its practical limitation arises because industrial electrification, storage and dispatch decisions endogenously reshape that curve, creating a potentially substantial gap between exogenous-profile booking and the coupled optimum.**

Diese Story ist methodisch präziser und stärker als eine rein deskriptive „AgNes verteuert/verbilligt Elektrifizierung“-Story.

---

# AD. Vollständige Prioritätenliste vor Submission

## 🔴 Zwingend
- Formeln korrigieren.
- Einheiten prüfen.
- Symbole definieren.
- \(\theta\)-Inkonsistenz prüfen.
- „unverified“ entfernen.
- StromNEV-Baseline sauber dokumentieren.
- Break-even korrekt benennen.
- CO₂-Break-even nicht aus 2/8 übergeneralisieren.
- Perfect Foresight / ex-ante-Widerspruch klar adressieren.
- Tarifniveau-Konfundierung offenlegen.
- Aggregierten Speicher-Systemwert korrigieren.
- statistische Generalisierung vermeiden.

## 🟠 Stark empfohlen
- StromNEV exakt enumerieren.
- 15-min-KPI-Vergleich erweitern.
- Fixpreis/DA preisniveau-neutralisieren.
- Endogeneity Gap definieren.
- Interaction mechanistisch erklären.
- Technologieannahmen tabellarisch darstellen.
- Lastjahre/Preisjahre transparent dokumentieren.
- praktische Regel als Screening-Regel formulieren.
- Ergebnisstruktur überarbeiten.
- Discussion schärfen.

## 🟡 Sinnvolle Verbesserung
- Titel schärfen.
- Abstract präzisieren.
- Elektrodenkessel-Sensitivität.
- Netzebenen-Sensitivität.
- normalisierte Kapazitätskennzahlen.
- bessere Abbildungen.
- synthetische Reproduktionsdaten.
- Terminologie vereinheitlichen.

## 🟢 Beibehalten / ausbauen
- analytische Bestellregel,
- reale Fabrikfälle,
- gekoppelte Systemoptimierung,
- 2×2-Netz-/Preisdesign,
- Ergebnisheterogenität,
- Open Code / Zenodo,
- exogen vs. coupled vs. realized comparison.

---

# AE. Schlussbewertung

## Was aktuell gut ist
- starke analytische Idee,
- relevante regulatorische Fragestellung,
- reale industrielle Daten,
- technisch sinnvolle Kopplung,
- interessante heterogene Ergebnisse,
- sehr gutes zentrales Resultat zur Endogenität der Lastdauerlinie.

## Was aktuell am meisten angreifbar ist
1. ex-ante-Bestellung unter Perfect Foresight,
2. nicht vollständig belastbare StromNEV-Baseline,
3. Tarifniveau vs. Tarifstruktur,
4. einzelne mathematische Inkonsistenzen,
5. Break-even-Bezeichnung,
6. zu geringe Erklärung der Standortheterogenität,
7. zu starke Schlussfolgerungen aus vier Fällen.

## Was ohne Methodenumbau unbedingt getan werden sollte
Das Manuskript kann bereits deutlich stärker werden, ohne das Studiendesign neu aufzubauen, wenn:
- Mathematik und Terminologie bereinigt,
- die Referenzfälle transparenter gemacht,
- die Interpretation vorsichtiger und mechanistischer formuliert,
- die 34,7-%-Abweichung korrekt als Endogenitätsproblem positioniert,
- und die Ergebnisse strukturell sauberer dargestellt werden.

## Was das Paper auf ein deutlich höheres Niveau heben würde
Falls eine zusätzliche methodische Erweiterung möglich ist:
- Forecast-/Ex-ante-Robustheit,
- revenue-neutral comparison,
- parametrische Mechanism Study.

