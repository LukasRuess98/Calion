# Plan: Von der Studie zu belastbaren Aussagen – Großwärmespeicher MAN/UPM, Netz Stadtbach

Stand: 2026-10-01 · Bezug: `Review_Studie_MAN_UPM.md` (Befunde 2.1–3.6) und Notebook `studie_grosswaermespeicher_MAN_UPM.ipynb` (Branch `claude/busy-shannon-9uws43`, Stand `121196e`). Der Plan ersetzt den Plan aus Kap. 23.1 der Studie (Phasen A–E) und schärft ihn.

---

## 1. Was heißt „richtige Aussage“?

### 1.1 Drei Aussagetypen mit eigenen Nachweisanforderungen

| Typ | Beispiel | Nachweis, bevor die Aussage in den Bericht darf |
|---|---|---|
| **P – Physik** | „Entladen ist ohne Pumpe hydraulisch unmöglich“ | Herleitung und Test. *Schon erfüllt.* |
| **V – Wirkung/Vergleich** | „Der Speicher am MAN hebt den kleinsten Kunden-Δp um x bar“, „Standort A wirkt stärker als B“, „Maßnahme M1 vor M2“ | (1) physikalisch konsistentes Modell (Massenbilanz je Erzeuger, eine Druckhaltung); (2) **Wirkung an realen Ereignissen validiert** (Abschnitt 4, Phase 3.2); (3) Aussage gilt in ≥ 90 % der Unsicherheitsläufe **und** in allen plausiblen Modellvarianten |
| **A – Absolut/Machbarkeit** | „Der Bestand erfüllt Δp_min bei −14 °C“, „Ausbau bis +x % möglich“, „Auslegungsdruck y bar“ | zusätzlich zu V: (4) Grenzwerte und Erzeugergrenzen vom Betreiber bestätigt; (5) Δp an den kritischen Stationen bei Hochlast validiert (RMSE ≤ 0,2 bar, Bias ≤ 0,1 bar); (6) Auslegungslast als Band; Angabe als P50/P90 |

Erfüllt eine Aussage die Kriterien nicht, wird sie **bedingt** formuliert: „Unter der Annahme …, gilt …“. Alternativ entfällt sie.

### 1.2 Fragestellung umdrehen: erforderliche Förderhöhe statt „Defizit bei festgehaltenem Druck“

Die Studie hält die Erzeugerdrücke fest (und verschlechtert sie pauschal um 0,65 bar) und misst dann ein „Δp-Defizit“. Damit hängt das Ergebnis an einer willkürlichen Annahme. Außerdem ist die Druckanhebung damit per Konstruktion die beste Maßnahme (Review 2.1/2.2).

**Richtig ist die Frage, wie der Betrieb sie stellt:**
* **Erforderliche Erzeuger-Förderhöhe:** Welche Druckdifferenz muss das HKW fahren, und welche Förderhöhen brauchen die Ost-Pumpen, damit **alle** Kunden am Schlechtpunkt Δp_min erhalten? Das wird mit dem **Verfügbaren** verglichen: Pumpenkennlinie, max. Δp am Werksaustritt (HKW 4,0 bar, Ost 7,5 bar laut WV640), Abschaltdrücke, PN.
* **Aufnahmekapazität:** Wie viel zusätzliche Last (MW) ist je Gebiet bei verfügbarer Förderhöhe möglich?
* **Wirkung jeder Maßnahme**, auch des Speichers: eingesparte Förderhöhe [bar] und zusätzliche Aufnahmekapazität [MW] je Gebiet, später in €/MW.

Damit entfällt S-05 als Annahme. Die Druckanhebung wird nicht mehr als Wirkung bewertet, sondern als **Machbarkeitsfrage** gegen Pumpenkennlinien und Grenzen.

### 1.3 Aussagenregister
Jede Aussage im Bericht bekommt einen Eintrag: Typ (P/V/A), Beleg (Zelle, Datei, Kennzahl), tragende Annahmen, Validierungsnachweis, Unsicherheitsband und Status. Der Bericht wird **aus** dem Register erzeugt, nicht umgekehrt. Ziel für die heutigen Kernaussagen siehe Abschnitt 6.

---

## 2. Phase 0 – Bewertungsrahmen festlegen (Woche 0–1, mit Auftraggeber)

Vor jeder weiteren Rechnung wird schriftlich vereinbart (2 Seiten, Freigabe durch den Auftraggeber = **Gate G0**):

| Punkt | Festzulegen |
|---|---|
| Leitfragen | F1: Reicht das Netz heute bei Auslegungslast mit den vorhandenen Pumpenreserven? F2: Wie viel Ausbau ist wo ohne Maßnahmen möglich? F3: Was bringt der Speicher am MAN im Vergleich zu Alternativen? F4: Welches Speicherkonzept und welcher Auslegungsdruck? F5: Welche Maßnahme(nkombination) ist je Ausbaupfad am günstigsten? |
| Auslegungsfall | Auslegungs-Außentemperatur (−14 °C?), **Auslegungstag und Auslegungswoche** (Kältewelle 3–5 Tage), Heizkurve im Betrieb |
| Grenzwerte | Kunden-Δp_min aus den TAB der swa (HWW-WÜ: 0,7 bar laut Plan), Siedeabstand, PN, Abschaltdrücke, Erzeugergrenzen |
| Ausbaupfade | konkrete Vorhaben (D1); andernfalls wird die Aufnahmekapazität je Gebiet berichtet |
| Speicherkonzepte | welche Varianten (Phase 5) überhaupt in Frage kommen (Fläche, Bauhöhe, Druckhaltung) |
| Maßnahmenkatalog | inkl. der in der Studie fehlenden Optionen Druckerhöhungsstation und Rücklauftemperaturabsenkung (Phase 6) |
| Kostenbasis | wer Kostenansätze liefert (F1/F2) |

Parallel geht die **Datenanfrage** an den Betreiber, reduziert auf das Entscheidende (Abschnitt 5).

---

## 3. Phase 1 – Sofortkorrekturen ohne Betreiberdaten (Woche 1–2)

| Nr. | Arbeitspaket | Ergebnis / Akzeptanz |
|---|---|---|
| 1.1 | Diagnose-Checks aus Review 6.1–6.3 ausführen: Massenbilanz je Erzeuger (VL gegen RL), minimale Druckrand-Einspeisung, f_m, S1 ohne S-05, S-05 aus Daten, HKW-Δp gegen 4,0 bar | Ergebnistabelle. Bestätigt oder widerlegt die Review-Befunde mit Zahlen |
| 1.2 | **S-05 als Annahme streichen.** Nur noch als datenbasierte Sensitivität führen (P5 der Erzeuger-Δp bei Hochlast relativ zum Basistag) | S1 = Basistag skaliert, ohne Abschlag |
| 1.3 | **Auslegungslast explizit:** `heat_factor` aus einer Regression auf **Tagesmittel** (T_a, Wochentag, Vortagstemperatur) statt Stundenwerten; Band P50/P90; f_m ausgeben | `LAST_MODELL` wird tatsächlich verwendet |
| 1.4 | **Erzeugergrenzen aus WV640:** Massenströme/Leistungen bei AT −14 °C, Δp am Werksaustritt (4,0/7,5 bar), VL-/RL-Abschaltdrücke als Nebenbedingungen in `evaluate` | keine Limits mehr aus 2025-P99,9 |
| 1.5 | Speicher-Auslegungsdruck korrekt ableiten (Review 6.4); Textfehler Antwort 15; Antworten 3, 4, 13, 18, 23 und Summary nach Aussagetyp umformulieren | „Stand 1“ des Berichts |
| 1.6 | Kalibrierung: nicht konvergierte Stunden bestrafen statt Residuum 0 setzen; Kap.-13-Text an den Code angleichen | Anteil Nichtkonvergenz ausgewiesen |
| 1.7 | **Code aus dem Notebook in ein Modul überführen** (z. B. `studien/stadtbach_hydraulik/`) mit Unit-Tests: Analytik (Parallelrohr, Ring), Massenbilanz je Erzeuger, Verschiebungsinvarianz (gleiche Randverschiebung ⇒ gleiche Knotenverschiebung), Speicherbilanz. Tests laufen mit einem **synthetischen** Stadtbach-ähnlichen Datensatz, damit sie ohne NDA-Daten in CI laufen | Notebook ruft nur noch das Modul auf. Grundlage für alle weiteren Phasen |

**Mögliche Aussagen nach Gate G1 (Ende Woche 2):** P-Aussagen und korrigierte V-Aussagen mit ausdrücklicher Bedingung, noch keine A-Aussagen.

---

## 4. Phasen 2–8

### Phase 2 – Konsistente Modellstruktur (Woche 2–6)

**2.1 Eine Druckhaltung, Massenbilanz je Erzeuger**

Formulierung je Stunde mit gleicher Einspeisung s im VL und −s im RL:

* HKW ist der einzige Druckrand: RL-Druckhöhe = Druckhaltung (Ruhedruck), VL-Druckhöhe = RL + Δp_HKW. HKW ist der **Slack**: Seine Einspeisung schließt die Bilanz und ist damit automatisch in VL und RL gleich.
* Ost-Erzeuger, zwei Varianten. Phase 3 entscheidet anhand der Daten, welche die gemessenen AVA-Drücke besser trifft; der Betreiber bestätigt das (A3).
  * **(a) massenstromgeführt:** AVA, GT, BM, HWS speisen den gemessenen bzw. aus Q/ΔT abgeleiteten Massenstrom ein. Ihre **erforderliche Förderhöhe** H_VL − H_RL am Erzeugerknoten ist Ergebnis und wird gegen 7,5 bar bzw. die Pumpenkennlinie geprüft.
  * **(b) Δp-geregelt:** Der Massenstrom der AVA wird je Stunde per 1-D-Nullstellensuche so bestimmt, dass H_VL − H_RL am AVA-Knoten dem gemessenen Wert entspricht. Er gilt in VL und RL gleichermaßen.
* Die gemessenen AVA- und Ost-Drücke werden damit **Validierungsziele** statt Randbedingungen. Die Offsets AVA_REF_VL/RL (−0,3/+7,7 m) entfallen.

Umsetzung mit dem vorhandenen Löser (geringer Aufwand). `solve_case(cfg=dict(ava_ref=False))` existiert bereits; statt `inj[AVA] = 0` wird der Massenstrom eingesetzt:
```python
CASE_COLS += ["m_ava"]                                   # AVA-Massenstrom in die Fälle übernehmen
# in solve_case, Zweig ava_ref=False:  inj[:, nidx["AVA"]] = cs.m_ava.values   (statt 0.0)
def solve_consistent(cs, dp_hkw_bar, m_stor=None, cfg=None):
    cs = cs.copy(); cs["pVL_hkw"] = cs.pRL_hkw + dp_hkw_bar      # VL am HKW = Druckhaltung + Δp-Sollwert
    return solve_case(cs, cfg=dict(cfg or {}, ava_ref=False), m_stor=m_stor)
```

**2.2 Schlechtpunktregelung als Szenariomodus**

Mit nur einem Druckrand und festen Lasten verschiebt eine Änderung von Δp_HKW **alle** VL-Druckhöhen gleichmäßig. Die erforderliche HKW-Druckdifferenz je Stunde ergibt sich deshalb ohne Iteration:
```python
res = solve_consistent(cs, dp0); dpk = kunden_dp(res)                       # Kunden-Δp inkl. Sektionsabschlag (2.3)
dp_hkw_erf = dp0 + (DP_MIN[None, :] - dpk).max(axis=1)                     # erforderliche HKW-Δp je Stunde (< dp0: Reserve)
# Ost-Förderhöhen verschieben sich um denselben Betrag → gegen 7,5 bar / Kennlinie prüfen
```
Im getrennten Betrieb (S7) hat die Ost-Insel keinen HKW-Bezug. Dort wird die AVA zum Druckhalter der Insel; dasselbe Verfahren gilt je Insel.
Kennzahlen je Szenario:
* max. erforderliche HKW-Δp gegen 4,0 bar bzw. die Kennlinie,
* max. erforderliche Ost-Förderhöhe gegen 7,5 bar,
* Druckniveau gegen PN und Abschaltdrücke,
* Reserve in bar.

Damit sind F1 und F2 direkt beantwortbar.

**2.3 Lastabhängiger Druckabfall innerhalb der Sektionen**

Die konstante Bias-Korrektur (M-11) wurde bei Last 2025 kalibriert. Bei Auslegungslast und Ausbau wächst der sektionsinterne Druckabfall quadratisch; die konstante Korrektur ist dann **nicht konservativ**. Ersatz:

Δp_Kunde,s = Δp_Knoten,s − c_s · (ṁ_s/ṁ_s,ref)^n, mit n ≈ 1,8–2.

c_s wird je Sektion aus den Messstationen gefittet (Hoher Weg, Fuggerstr., Hunoldsgraben, Kreissparkasse → SEC2; Theodor-Heuss-Platz → SEC4; UNI, SIGMA → SUED; …). Sektionen ohne Station erhalten ein Band aus vergleichbaren Sektionen.

**2.4 Lastverteilung**
* Lastanteile mit plausiblen Auslastungsbändern begrenzen (z. B. 0,3–0,7 der Anschlussleistung im Wintermedian, Industrie separat).
* Zeitvariable Anteile für Industrie- und Wohnlast.
* Die 17 geschätzten Kundenreihen aus `combined` als Prior nutzen.
* Mindestens drei Lastvarianten als Strukturensemble mitführen.

**2.5 Höhen**
* Geländehöhen aller Knoten und Stationen aus dem **DGM1 (OpenData Bayern; Verfügbarkeit und Lizenz prüfen)**.
* Mit den aus Schwachlast abgeleiteten Höhen vergleichen. Schwachlastfilter zusätzlich mit kleinem |SL1|-Fluss.
* Hochpunkte für die Siedesicherheit bestimmen.

**2.6 Einheiten und Dichte:** Dichte am Messort verwenden. Bis zur Betreiberbestätigung (E1) m³/h und t/h als zwei Varianten führen.

**2.7 Strukturell unabhängige Gegenrechnung:** pandapipes als **geschlossener Kreis**, also VL und RL in einem Netz mit Wärmeverbrauchern, einer Umwälzpumpe mit Druckhaltung am HKW und massenstromgeführten Pumpen an den Ost-Erzeugern. Damit prüft pandapipes die Modellannahmen, nicht nur die Numerik.

**Akzeptanz Phase 2:**
* Massenbilanz je Erzeuger exakt (< 0,1 kg/s).
* Kein Kalibrierparameter an einer Grenze; k_g etwa im Bereich 0,5–2.
* Auslastungen plausibel.
* RMS der normierten Residuen ≤ 1,5.
* pandapipes (geschlossener Kreis) ≤ 0,05 bar.

### Phase 3 – Validierung der entscheidungsrelevanten Größen (Woche 5–8)

| Nr. | Prüfung | Kriterium |
|---|---|---|
| 3.1 | **Zustand:** Kunden-Δp an den kritischen Stationen in den Hochlaststunden. Holdout: Februar-Spitzenwoche **und** Okt–Dez; zusätzlich Leave-one-Station-out | RMSE ≤ 0,2 bar, \|Bias\| ≤ 0,1 bar je kritischer Station |
| 3.2 | **Wirkung (Netzhebel) an natürlichen Experimenten:** Stunden, in denen sich eine lokale Einspeisung sprunghaft ändert, bei sonst stabiler Last. **Heizwerk Süd Ein/Aus** ist das direkte Analogon zu „Speicher entlädt lokal“. Dazu GT-Ost Start/Stopp, PSS-Pumpe zu/ab, HKW-Δp-Sprünge. Je Ereignis gemessene gegen modellierte Δp-Änderung an allen Stationen (Fenster ±2 h, lastbereinigt) | Vorzeichen stimmt in ≥ 90 % der Fälle; Betrag innerhalb ±30 % bzw. ±0,05 bar. **Ohne diesen Nachweis ist keine Aussage über die Speicherwirkung belastbar** |
| 3.3 | **Feldtest mit dem Betreiber (empfohlen):** Sollwertsprung HKW-Δp ±0,2 bar über 2–3 h; Leistungssprung HWS; Minutenwerte an den kritischen Stationen und an Arm. 342.x (E2) | wie 3.2, mit geringerem Rauschen |
| 3.4 | Ost-Erzeuger: modellierte gegen gemessene Förderhöhe bzw. Drücke an AVA/GT/BM (jetzt Validierungsziele) | entscheidet Variante (a) oder (b) aus 2.1 |

**Gate G2 (Woche 8):**
* 3.1 und 3.2 erfüllt: V- und A-Aussagen sind für die validierten Bereiche zulässig.
* Nur 3.2 erfüllt: V-Aussagen mit Band zulässig, A-Aussagen nur bedingt.
* 3.2 nicht erfüllt: Messkampagne (3.3) vor weiteren Aussagen zur Speicherwirkung.

### Phase 4 – Auslegungsfall und Szenarien (Woche 6–9)

* **4.1 Auslegungslast:**
  * Tagesmittel-Regression,
  * Lastgänge 2020–2022 (Definition klären, D3),
  * historische Kältewellen aus den DWD-Klimadaten (Station Augsburg),
  * Plausibilisierung über Anschlussleistung × Gleichzeitigkeit.

  Ergebnis: Auslegungstag **und** Auslegungswoche, jeweils P50/P90.
* **4.2 Betriebsweise:**
  * Heizkurve wie tatsächlich gefahren,
  * Rücklauftemperatur lastabhängig aus Daten regressiert (statt konstant),
  * Erzeugereinsatz nach Merit-Order (AVA must-run, BM, GT, HKW als Swing, HWS Spitze) innerhalb der Plangrenzen.
* **4.3 Ausbau:** Ausbaupfade aus D1; andernfalls Aufnahmekapazität je Gebiet. Diese Kenngröße hängt nicht von unbekannten Vorhaben ab.
* **4.4 Schaltzustände** nach B1 (Betriebsanweisung) statt Annahme S7-1/S7-2.

### Phase 5 – Speicherkonzept (Woche 6–10, mit Auftraggeber und Planer)

| Konzept | Hydraulisches Ersatzmodell | Auslegungsdruck | Pumpen |
|---|---|---|---|
| K1 direkt, mehrere schlanke Druckbehälter auf Netzdruck | Einspeisung/Entnahme am Knoten (wie heute) | ≈ p_VL,max + Strangverluste + Absperrreserve | Entladepumpe |
| K2 druckentkoppelt (Speicher bei niedrigem Druck, ≥ p_sat + Abstand) | Einspeisung/Entnahme, beide Richtungen gepumpt bzw. gedrosselt | niedrig (≈ 3–5 bar Ü) | Lade- **und** Entladepumpe; Variante A entfällt |
| K3 atmosphärisch ≤ 95 °C mit Nacherhitzung oder indirekt | Einspeisung mit begrenzter Temperatur; Nachheizung (z. B. Elektrodenkessel) | atmosphärisch | wie K2 |
| K4 Speicher als Druckhaltung | Druckrand am MAN statt (oder neben) HKW | Netzdruck | – |

Je Konzept wird bestimmt:
* Auslegungsdruck korrekt aus Saugdruck + Absperrhöhe bzw. Sicherheitsventil,
* Platzbedarf, Behälteranzahl,
* **Mehrtagesbetrieb** über die Auslegungswoche (rollierende Optimierung; kann in der Kältewelle nachgeladen werden?),
* später die Druckstoßstudie.

Erst danach folgt die Pumpenauslegung.

### Phase 6 – Maßnahmenvergleich (Woche 9–13)

**6.1 Maßnahmenkatalog** (erweitert um bisher fehlende, oft günstigere Optionen):
* Druckanhebung im Rahmen der Pumpenreserve; Pumpentausch HKW/Ost
* **Druckerhöhungsstation (Booster)** im Zulauf des kritischen Gebiets. Das ist das direkte Gegenstück zum „Speicher mit Pumpe“, nur ohne Speicher.
* **Rücklauftemperaturabsenkung**: −5 K bei 120/55 °C ⇒ ≈ −7 % Massenstrom, ≈ −14 % Reibungsverlust im ganzen Netz
* gezielte Leitungsverstärkung an den Engpasskanten aus 2.2
* Erzeugerverlagerung (HWS, dezentrale Power-to-Heat-Anlagen)
* Speicher am MAN bzw. am besten Standort; Kombinationen

**6.2 Kennzahlen je Maßnahme und Ausbaustufe:**
* eingesparte erforderliche Förderhöhe [bar],
* zusätzliche Aufnahmekapazität [MW] je Gebiet,
* Machbarkeit gegen die Grenzen,
* mit Kosten (F1/F2): **€ je MW Aufnahmekapazität**.

**6.3 Robuste Rangfolge:** Für jede Maßnahme die Wahrscheinlichkeit, dass sie ausreicht bzw. die günstigste ist, über das Unsicherheitsensemble (Phase 7). Berichtet werden nur Rangfolgen mit ≥ 90 % Stabilität.

**6.4 Energiewirtschaftlicher Nutzen des Speichers getrennt bewerten:**
* Einsatzoptimierung mit Wärmepumpen und Elektrodenkesseln im Calion-Framework,
* die hydraulischen Restriktionen aus dem Netzmodell gehen als linearisierte Nebenbedingungen ein (Sensitivitäten wie in Kap. 17).

Ein Speicher kann wirtschaftlich sinnvoll sein, auch wenn sein hydraulischer Nutzen klein ist. Beide Fragen dürfen nicht vermischt werden.

### Phase 7 – Unsicherheit (laufend, Abschluss Woche 12–14)

* **Parameter:** Kalibrierensemble per **Block-Bootstrap über Tage** (20–30 Neukalibrierungen). Das ersetzt die unabhängige Ziehung, die Korrelationen ignoriert.
* **Struktur:** Ensemble der Modellvarianten:
  * Ost (a)/(b),
  * ≥ 3 Lastverteilungen,
  * Höhen aus DGM bzw. abgeleitet,
  * Durchflusseinheit.
* **Szenario:** Auslegungslast P50/P90, Ausbaupfade, Rücklauftemperatur, Δp_min laut TAB ± Band.
* **Ausgabe:** P10/P50/P90 der Entscheidungsgrößen (erforderliche Förderhöhe, Aufnahmekapazität, Speicherwirkung) und Wahrscheinlichkeiten für V-Aussagen.

### Phase 8 – Qualitätssicherung und Bericht (Woche 13–16)

* Aussagenregister vollständig; der Bericht wird daraus erzeugt.
* Tests und CI (synthetischer Datensatz), versionierte Ergebnisse mit Konfigurations-Hash.
* **Plausibilisierung durch den Betreiber:** Stimmt der berechnete Schlechtpunkt mit dem bekannten überein? Passen die erforderlichen Förderhöhen zu den gefahrenen Sollwerten im Winter?
* Vier-Augen-Prüfung der Kernrechnungen.

---

## 5. Datenbedarf – das Entscheidende zuerst

| Prio | Information (Nr. der Datenanfrage) | wird gebraucht für |
|---|---|---|
| 1 | Kunden-Δp_min laut TAB bzw. Vertrag; Alarm- oder Beschwerdegrenze (D2, G6) | Kriterium aller A-Aussagen |
| 1 | Pumpenkennlinien und Δp-/Abschaltgrenzen HKW, Ost, PSS/PSW (A1, A2) | Machbarkeit (2.2, 6) |
| 1 | Regelphilosophie Ost: massenstrom- oder Δp-geführt; Schlechtpunkt-Sollwerte (A3) | Modellstruktur (2.1) |
| 1 | Speicherkonzept und Fläche (C1, C2) | Phase 5 |
| 2 | Minutenwerte an kritischen Stationen und Feldtest-Bereitschaft (E2) | Validierung (3.2/3.3) |
| 2 | Schaltzustände und Betriebsanweisung Trennung (B1) | Szenarien |
| 2 | Ausbauvorhaben (D1), Kosten (F1/F2) | Phase 6 |
| 3 | GIS-Leitungsdaten (B3); Geländehöhen (B4), notfalls DGM1 OpenData | Feinschliff |

Ohne Betreiberdaten möglich: Phasen 1, 2 (mit Varianten), 3.1/3.2 (natürliche Experimente), 4.1 (DWD), 2.5 (DGM1) und 7. Ohne Betreiberdaten **nicht** möglich: die Machbarkeit der Druckanhebung (A-Aussagen zu F1/F2), die Entscheidung zwischen den Speicherkonzepten und die Kostenrangfolge.

---

## 6. Zielzustand der heutigen Kernaussagen

| Heutige Aussage der Studie | Problem (Review) | Weg zur belastbaren Aussage | Phase | Zieltyp |
|---|---|---|---|---|
| Entladen nur mit Pumpe | – | bleibt; im konsistenten Modell erneut bestätigen | 2 | P |
| Laden zur Lastspitze schädlich | – | im konsistenten Modell bestätigen | 2 | P/V |
| Speicherwirkung +0,1…0,2 bar | Netzhebel nicht validiert; Struktur (2.3) | Netzhebel an HWS-/GT-Ereignissen validieren; als eingesparte Förderhöhe bzw. Aufnahmekapazität ausdrücken; Ensemble | 2, 3, 7 | V |
| Bestand kritisch, Defizit 15–19 bar·h | S-05, Auslegungsfall (2.1) | erforderliche HKW-Δp bei Auslegungslast P50/P90 gegen 4,0 bar bzw. Kennlinie | 1, 2, 4 | A |
| Ausbau nur bis +5…10 % | S-05, S-02, Ausbauort | Aufnahmekapazität je Gebiet bei verfügbarer Förderhöhe | 2, 4, 6 | A |
| HKW-Limit ab +15 % | Limit = 2025-Beobachtung (2.2) | Plangrenzen und Merit-Order | 1, 4 | A |
| Druckanhebung ist der Haupthebel | per Konstruktion (2.2) | Machbarkeit gegen Kennlinien und Grenzen; Kostenvergleich mit Booster und Rücklaufabsenkung | 1, 6 | A/V |
| Standort Innenstadt wirkt stärker | Lastverteilung nicht identifizierbar (3.4) | Lastvarianten im Ensemble; reale Standortflächen | 2, 5, 7 | V |
| Auslegungsdruck ≈ 17 bar | Formel (2.4) | Konzept K1–K4, korrekte Ableitung, Druckstoß | 1, 5 | A |
| Siedesicherheit gegeben | Höhen abgeleitet | DGM-Höhen, Hochpunkte | 2 | A |

---

## 7. Zeitplan und Entscheidungspunkte (grobe Schätzung)

| Woche | 0–1 | 1–2 | 2–6 | 5–8 | 6–10 | 9–13 | 12–14 | 13–16 |
|---|---|---|---|---|---|---|---|---|
| Phase | 0 Rahmen | 1 Sofortkorrektur | 2 Struktur | 3 Validierung | 4 Szenarien / 5 Konzept | 6 Maßnahmen | 7 Unsicherheit | 8 QS/Bericht |

| Gate | Woche | Entscheidung | Danach zulässige Aussagen |
|---|---|---|---|
| G0 | 1 | Bewertungsrahmen freigegeben | – |
| G1 | 2 | Sofortkorrekturen abgeschlossen, Stand 1 | P; V bedingt |
| G2 | 8 | Modellgüte (3.1/3.2) erreicht? Sonst Messkampagne | V belastbar; A für validierte Bereiche |
| G3 | 13 | Maßnahmenrangfolge stabil (≥ 90 %)? Speicher weiterverfolgen? | Rangfolge technisch; mit Kosten wirtschaftlich |
| G4 | 16 | Abschlussbericht aus dem Aussagenregister | alle Aussagen mit Typ und Band |

Aufwand grob 60–90 Personentage (Phase 1: 5–8, Phase 2: 15–25, Phase 3: 8–12, Phase 4: 6–10, Phase 5: 5–10 ohne Planer, Phase 6: 8–12, Phase 7: 5–8, Phase 8: 5–8). Er hängt stark von der Datenlieferung des Betreibers ab.

---

## 8. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Betreiberdaten (A1–A3) kommen spät oder gar nicht | Phasen 1–3 laufen ohne sie; A-Aussagen bleiben bedingt formuliert („bei verfügbarer Förderhöhe von x bar …“) |
| Zu wenige saubere natürliche Experimente für 3.2 | Feldtest 3.3 (wenige Stunden, geringer Aufwand für den Betreiber) |
| Ostbereich auch mit konsistenter Struktur nicht validierbar | Aussagen räumlich begrenzen (Mitte/Süd/MAN); Ost nur als Band; gezielte Messung an Arm. 342.x und den Ost-Koppelstellen |
| Stundenwerte zu grob für Spitzen-Δp | Stunden-Min/Max (`acron_stundenwerte_minmax`) oder Minutenwerte nutzen |
| Kosten fehlen | technische Rangfolge mit Machbarkeit berichten; Kostenrangfolge als offener Punkt |
