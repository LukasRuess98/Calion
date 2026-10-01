# Plan: Von der Studie zu belastbaren Aussagen – Großwärmespeicher MAN/UPM, Netz Stadtbach

Stand: 2026-10-01, **Version 2 nach Prüfung mit den Messdaten 2025 und den Plänen WV640/650/660** · Bezug: `Review_Studie_MAN_UPM.md` (Befunde 2.1–3.6, Datenprüfung Abschnitt 9) und Notebook `studie_grosswaermespeicher_MAN_UPM.ipynb` (Branch `claude/busy-shannon-9uws43`, Stand `121196e`). Der Plan ersetzt den Plan aus Kap. 23.1 der Studie (Phasen A–E) und schärft ihn.

**Hinweis zur Weitergabe:** Der Plan enthält aggregierte, aus NDA-Daten abgeleitete Kennzahlen. Vor externer Weitergabe freigeben lassen.

**Was sich mit den Daten geändert hat (Kurzfassung):**
* Die Review-Befunde sind bestätigt.
* Die Daten liefern bereits **Validierungsziele** (gemessene Netzhebel, Temperatur-Tracer, Regelkennlinie des HKW) und einen **Plausibilitätsanker** für die Kernfrage.
* Sie zeigen einen **Signalfehler** (GT-Wärme), der vor jeder Neukalibrierung behoben sein muss.
* Der Schwerpunkt verschiebt sich: Nach den Daten ist der **Bestand nicht kritisch**. Die eigentlichen Fragen sind die **Aufnahmekapazität beim Ausbau** (HKW-Δp-Grenze 4,0 bar, ausgelastete Ost-Erzeuger) und der **Süden** (Fraunhofer, PSS/HWS).

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

**Die Daten stützen diese Umstellung** (Review 9.2, N3): Das HKW fährt seine Δp lastabhängig von ≈ 1,8 auf ≈ 2,9 bar hoch, während die Kunden-Δp in der Mitte über alle Lastbereiche bei ≈ 1,6–1,8 bar (P10 1,2–1,5) bleiben. Der Betrieb hält also den Kunden-Δp und lässt die Erzeugerdrücke frei. Genau das bildet die Frage „erforderliche Förderhöhe“ ab.

### 1.4 Was die Daten heute schon zeigen (Review Abschnitt 9)

| Befund aus den Daten | Bedeutung für den Plan |
|---|---|
| `GT-Ost_Waermeleistung` ist eine Kopie von `HWW_Waermeleistung_Sek_Aussp` | vor jeder Rechnung beheben (1.8): GT-Einspeisung, Ost-Erzeugung und Last sind sonst falsch |
| Die HKW ist laut WV640/WV650 einziger Druckhalter; AVA, GT und HWS nur im Not- bzw. Inselbetrieb | Struktur 2.1 (HKW als Slack) ist **durch die Pläne vorgegeben**, keine Variante mehr |
| S-05 empirisch: HKW-Δp-P5 nur −0,18 bar, AVA −0,33 bar unter dem Basistag; die angenommene Kombination trat nie auf | S-05 entfällt (1.2) |
| Basistag 14.02.: f_m = 0,86; 215 MW nicht reproduzierbar (≈ 169 MW nach Studiendefinition) | Basistag und Auslegungslast neu ableiten (1.3, 1.11) |
| HKW-Δp 2025 in Hochlast P95 3,2 bar → Reserve ≈ 0,8 bar bis 4,0 bar; HKW-Wärme P99 62 von 127 MW | HKW hat Leistungs- und Druckreserve; die Grenze ist eher die Δp am HKW-Austritt |
| AVA, BM und HWS lagen 2025 an ihren Planleistungen; AVA-Δp in 390–550 h über 7,5 bar | Ausbaulast muss vom HKW kommen; Ost-Förderhöhe ist knapp, und 7,5 bar ist keine harte Grenze → klären (A2) |
| Durchfluss in t/h (Kundenstationen: Abweichung 0,1–0,3 %), SL-Messung im Rücklauf (WV650) | Massenströme ≈ 4–5 % höher ansetzen (1.9) |
| Fraunhofer (Süd) ist die kritischste Station (P1 0,9 bar) und wird nicht genutzt; HWW-Prim < 1,0 bar in 276 h | DiffDruck-Stationen einbeziehen (1.10); Δp_min je Knoten (TAB; HWW 0,7 bar) |
| Gemessene Netzhebel (Tabelle in 3.2) | **Validierungsziele** für jedes Modell (3.2) |
| Temperatur-Tracer: Ost-Wasseranteil MAN ≈ 75 %, Schlettererstr. ≈ 49 %, City (Kreissparkasse) ≈ 28 % | Validierungsziel für die Verbundflüsse und die Lastverteilung (3.5) |
| Anker: erforderliche HKW-Δp für 1,0 bar City ≈ 2,7 bar (Last 2025), ≈ 3,3 bar (+20 %), ≈ 4,1 bar (+40 %) | Modell muss diesen Anker reproduzieren (3.6); die Kernfrage F2 liegt damit im Bereich +20…40 % |

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
| **Rückfragen aus der Datenprüfung** | (1) Korrektes GT-Wärmesignal (das gelieferte ist eine Kopie der HWW-Sekundärwärme). (2) Ist 4,0 bar am HKW-Austritt eine harte Grenze oder ein Erfahrungswert (Fußnote WV640)? Warum lag die AVA-Δp in 390–550 h über 7,5 bar? (3) Auslegungs-Vorlauftemperatur am HKW: 107 °C laut WV640 („127 MW bei 107–60 °C“) oder 120 °C laut Vorgabe? (4) Gilt der Auslegungsfall als n−1 („bei Ausfall der größten Erzeugungsleistung“)? (5) Regelung des HKW: Schlechtpunkt- oder Kennlinienregelung, auf welche Stationen? |

Parallel geht die **Datenanfrage** an den Betreiber, reduziert auf das Entscheidende (Abschnitt 5).

---

## 3. Phase 1 – Sofortkorrekturen ohne Betreiberdaten (Woche 1–2)

| Nr. | Arbeitspaket | Ergebnis / Akzeptanz |
|---|---|---|
| 1.1 | Diagnose-Checks aus Review 6.1 ausführen: Massenbilanz je Erzeuger (VL gegen RL), minimale Druckrand-Einspeisung. *S-05, f_m und HKW-Δp gegen 4,0 bar sind bereits aus den Daten geprüft (Review 9.1).* | Ergebnistabelle |
| 1.2 | **S-05 als Annahme streichen.** Nur noch als datenbasierte Sensitivität führen: HKW −0,18 bar, AVA −0,33 bar Δp (P5 Hochlast gegen Basistag) | S1 = Basistag skaliert, ohne Abschlag |
| 1.3 | **Auslegungslast explizit:** `heat_factor` aus einer Regression auf **Tagesmittel** (T_a, Wochentag, Vortagstemperatur) statt Stundenwerten; Band P50/P90; f_m ausgeben | `LAST_MODELL` wird tatsächlich verwendet |
| 1.4 | **Erzeugergrenzen aus WV640:** Massenströme/Leistungen bei AT −14 °C, Δp am Werksaustritt (4,0/7,5 bar), VL-/RL-Abschaltdrücke als Nebenbedingungen in `evaluate` | keine Limits mehr aus 2025-P99,9 |
| 1.5 | Speicher-Auslegungsdruck korrekt ableiten (Review 6.4); Textfehler Antwort 15; Antworten 3, 4, 13, 18, 23 und Summary nach Aussagetyp umformulieren | „Stand 1“ des Berichts |
| 1.6 | Kalibrierung: nicht konvergierte Stunden bestrafen statt Residuum 0 setzen; Kap.-13-Text an den Code angleichen | Anteil Nichtkonvergenz ausgewiesen |
| 1.7 | **Code aus dem Notebook in ein Modul überführen** (z. B. `studien/stadtbach_hydraulik/`) mit Unit-Tests: Analytik (Parallelrohr, Ring), Massenbilanz je Erzeuger, Verschiebungsinvarianz (gleiche Randverschiebung ⇒ gleiche Knotenverschiebung), Speicherbilanz. Tests laufen mit einem **synthetischen** Stadtbach-ähnlichen Datensatz, damit sie ohne NDA-Daten in CI laufen | Notebook ruft nur noch das Modul auf. Grundlage für alle weiteren Phasen |
| 1.8 | **GT-Signal korrigieren:** `GT-Ost_Waermeleistung` verwerfen (Kopie von HWW-Sek). GT-Wärme und -Massenstrom aus `GT-Ost_Durchfluss`·Δh (35 % Abdeckung). Stillstand bei T_VL < 60 °C ⇒ 0. Übrige Stunden als fehlend markieren, beim Betreiber das richtige Signal anfordern. Folgerechnungen neu: Ost-Erzeugung, Restlast R, Gesamterzeugung, Lastregression | Prüfsumme: Ost-Erzeugung im Wintermedian ≈ 88 MW statt 77 MW |
| 1.9 | **Einheit t/h** für alle Kunden- und SL-Durchflüsse (BM-HKW: m³/h im VL). Dichte am Messort; die SL-Messung liegt im Rücklauf (WV650) | Einheitentest je Station ≈ 1,00 |
| 1.10 | **DiffDruck-Stationen einbeziehen:** Fraunhofer, Hoher Weg, Hunoldsgraben, KUKA, Don Bosco. Δp-Residuen direkt aus `DiffDruck` statt nur aus VL − RL | Fraunhofer als kritischer Süd-Knoten in Kalibrierung, Bias und Kriterium |
| 1.11 | **Basistag neu wählen:** nach korrigierter Erzeugung unter den vollständig gemessenen Tagen (Kandidaten 17.–19.02., 31.12.2025). Das Tagesmittel dokumentieren | 215-MW-Angabe ersetzt |
| 1.12 | **Δp_min je Knoten** aus der TAB; HWW 0,7 bar (WV640). Bis zur TAB-Klärung als Band 0,8–1,2 bar | Kriterium knotenweise statt pauschal |

**Mögliche Aussagen nach Gate G1 (Ende Woche 2):**
* P-Aussagen und korrigierte V-Aussagen mit ausdrücklicher Bedingung.
* Zusätzlich **datengestützte Aussagen zum Ist-Zustand 2025**: Druckreserve am HKW, Fraunhofer als kritische Station, Ost-Erzeuger an der Grenze, gemessene Netzhebel.
* Noch keine Aussagen zum Auslegungsfall.

---

## 4. Phasen 2–8

### Phase 2 – Konsistente Modellstruktur (Woche 2–6)

**2.1 Eine Druckhaltung, Massenbilanz je Erzeuger**

Formulierung je Stunde mit gleicher Einspeisung s im VL und −s im RL:

* HKW ist der einzige Druckrand: RL-Druckhöhe = Druckhaltung (Ruhedruck), VL-Druckhöhe = RL + Δp_HKW. HKW ist der **Slack**: Seine Einspeisung schließt die Bilanz und ist damit automatisch in VL und RL gleich. **Durch die Pläne bestätigt:** WV640 „Ruhedruckanbindung auf P-Saugseite“ (HKW), AVA „Ruhedruck (Notbetrieb)“, GT und HWS „(Inselbetrieb)“; WV650 „RL-Absperrarmatur muss zur Sicherstellung der Druckhaltung offen bleiben“.
* Ost-Erzeuger und HWS speisen höchstens ihre Planleistung ein; 2025 lagen sie bereits an der Grenze (AVA 46 MW, BM 15,4 MW, HWS 569 t/h). Zusatzlast geht damit an das HKW.
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

Die Daten zeigen, dass die HKW-Δp nur mit dem Faktor 0,70–0,84 auf die Kunden durchwirkt (Review 9.2, N4), weil die Ost-Erzeuger mitregeln. In Variante (b) aus 2.1 ist die Verschiebung daher nicht mehr exakt gleichmäßig. Dann gilt: 1-D-Nullstellensuche auf Δp_HKW statt der geschlossenen Formel.

Kennzahlen je Szenario:
* max. erforderliche HKW-Δp gegen 4,0 bar bzw. die Kennlinie,
* max. erforderliche Ost-Förderhöhe gegen 7,5 bar,
* Druckniveau gegen PN und Abschaltdrücke (AVA RL < 5,0 bar, HWS RL < 4,0 bzw. > 12,0 bar, PSS/PSW Saugseite < 5,0 bar; jeweils mit dem Bezugsniveau aus WV640),
* Ruhedruck am HKW gegen den Mindest-Ruhedruck je Netzbereich aus WV650 (City 6,5 bar bei 120 °C),
* Reserve in bar.

Damit sind F1 und F2 direkt beantwortbar.

**2.3 Lastabhängiger Druckabfall innerhalb der Sektionen**

Die konstante Bias-Korrektur (M-11) wurde bei Last 2025 kalibriert. Bei Auslegungslast und Ausbau wächst der sektionsinterne Druckabfall quadratisch; die konstante Korrektur ist dann **nicht konservativ**. Ersatz:

Δp_Kunde,s = Δp_Knoten,s − c_s · (ṁ_s/ṁ_s,ref)^n, mit n ≈ 1,8–2.

c_s wird je Sektion aus den Messstationen gefittet (Hoher Weg, Fuggerstr., Hunoldsgraben → SEC2; Theodor-Heuss-Platz → SEC4; **Fraunhofer**, UNI, SIGMA → SUED; Don Bosco, Lechhauser → SEC3; KUKA → SL7G). Sektionen ohne Station erhalten ein Band aus vergleichbaren Sektionen.

Die Daten bestätigen die Lastabhängigkeit: Die Differenz HKW-Δp minus ungünstigste Mitte-Station steigt von ≈ 0,2 bar (Schwachlast) auf ≈ 1,0 bar (Hochlast).

**2.4 Lastverteilung**
* Die Energiebilanz 2025 zeigt das Problem (Review 9.1): Ost erzeugt im Winter ≈ 89 MW, nur ≈ 4 MW davon fließen über SL1/SL3 ins HKW; SL2 liefert nur 25 MW für 151 MW Anschluss. Entweder ist die City sehr schwach ausgelastet (0,16), oder **≈ 30–45 MW fließen über die Verbundkanten** in die City. Der Temperatur-Tracer spricht für Letzteres.
* Lastanteile mit plausiblen Auslastungsbändern begrenzen (z. B. 0,3–0,7 der Anschlussleistung im Wintermedian, Industrie separat). MAN (32 MW Anschluss, ≈ 5 MW Wintermedian) dabei gesondert führen.
* Zeitvariable Anteile für Industrie- und Wohnlast.
* Die 17 geschätzten Kundenreihen aus `combined` als Prior nutzen.
* Mindestens drei Lastvarianten als Strukturensemble mitführen.

**2.5 Höhen**
* Geländehöhen aller Knoten und Stationen aus dem **DGM1 (OpenData Bayern; Verfügbarkeit und Lizenz prüfen)**.
* Mit den aus Schwachlast abgeleiteten Höhen vergleichen. Schwachlastfilter zusätzlich mit kleinem |SL1|-Fluss.
* Hochpunkte für die Siedesicherheit bestimmen.

**2.6 Einheiten und Dichte:** erledigt durch 1.9 (t/h; Messort Rücklauf). Nur noch BM-HKW in m³/h im VL.

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
| 3.2 | **Wirkung (Netzhebel) an natürlichen Experimenten:** Das Modell muss die **gemessenen Hebel** (Tabelle unten) reproduzieren. Im Modell gleiche Regression auf die simulierten Stunden anwenden oder die Sensitivitäten direkt bilden (∂Δp_Station/∂ṁ_HWS, ∂/∂Δp_HKW, ∂/∂Δp_AVA, ∂/∂PSS-Gewinn) | Vorzeichen in allen Fällen richtig; Betrag ±30 % bzw. ±0,05 bar. **Ohne diesen Nachweis ist keine Aussage über die Speicherwirkung belastbar** |
| 3.3 | **Feldtest mit dem Betreiber (empfohlen):** Sollwertsprung HKW-Δp ±0,2 bar über 2–3 h; Leistungssprung HWS; Minutenwerte an den kritischen Stationen und an Arm. 342.x (E2). Damit lässt sich insbesondere ein Hebel für eine Einspeisung **am MAN bzw. im Osten** bestimmen; der HWS-Hebel deckt nur den Süden ab | wie 3.2, mit geringerem Rauschen |
| 3.4 | Ost-Erzeuger: modellierte gegen gemessene Förderhöhe bzw. Drücke an AVA/GT/BM (jetzt Validierungsziele) | entscheidet Variante (a) oder (b) aus 2.1 |
| 3.5 | **Temperatur-Tracer:** Ost-Wasseranteil an den Stationen in Stunden mit T_Ost ≠ T_HKW. Gemessen: MAN ≈ 75 %, Hans-Böckler ≈ 85 %, Lechhauser ≈ 64 %, Schlettererstr. ≈ 49 %, Kreissparkasse (City) ≈ 28 %. Das Modell berechnet die Mischungsanteile aus seinen Flüssen (Aufwind-Mischung, wie `transport_T`, mit Quellmarkierung). Mit 15-min-Daten deutlich schärfer | Anteile ±15 Prozentpunkte. **Bestimmt die Verbundflüsse und damit die Lastverteilung** (2.4) |
| 3.6 | **Plausibilitätsanker** (Review 9.2, N7): Verlust HKW → ungünstigste Mitte-Station ≈ 0,28 + 4,1·10⁻⁵·P² bar über die Verbundeinspeisung P | Modell trifft den Verlauf im Bereich 2025 auf ±0,2 bar |

**Gemessene Netzhebel 2025** (Regression auf stündliche Differenzen, n ≈ 4 900 h; Review 9.2, N4):

| Station | je 100 kg/s HWS | je bar HKW-Δp | je bar AVA-Δp | je bar PSS-Gewinn |
|---|---|---|---|---|
| Fraunhofer (Süd) | +1,01 | 0,69 | −0,05 | +0,30 |
| City (Hoher Weg, Hunoldsgraben, Fuggerstr.) | +0,07…0,12 | 0,84 | 0,03…0,05 | −0,11…−0,12 |
| Theodor-Heuss-Pl. (SL4) | +0,06 | 0,84 | 0,03 | −0,13 |
| Schlettererstr. (SL1) | +0,02 | 0,84 | 0,02 | −0,12 |
| MAN | +0,04 | 0,74 | 0,19 | −0,07 |
| Lechhauser (STAWA) | +0,11 | 0,75 | 0,19 | −0,06 |

**Gate G2 (Woche 8):**
* 3.1 und 3.2 erfüllt: V- und A-Aussagen sind für die validierten Bereiche zulässig.
* Nur 3.2 erfüllt: V-Aussagen mit Band zulässig, A-Aussagen nur bedingt.
* 3.2 nicht erfüllt: Messkampagne (3.3) vor weiteren Aussagen zur Speicherwirkung.

### Phase 4 – Auslegungsfall und Szenarien (Woche 6–9)

* **4.1 Auslegungslast:**
  * mit korrigierter Erzeugung (1.8). Die Außentemperatur fehlt in den gelieferten Daten: `Import_Data_stadtbach_15min` nachliefern oder DWD-Station Augsburg verwenden,
  * Auslegungsfall nach WV640 als **n−1** („bei Ausfall der größten Erzeugungsleistung“) prüfen,
  * Auslegungs-Vorlauftemperatur am HKW klären (107 °C laut WV640 gegen 120 °C laut Vorgabe; 2025 in Hochlast Median 111,7 °C, nur 42 h ≥ 120 °C),
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
* Druckanhebung im Rahmen der Pumpenreserve (HKW 2025: ≈ 0,8 bar bis 4,0 bar; HKW-Pumpen 2×1000 + 2×900 t/h bei 73,5 m); Pumpentausch HKW/Ost
* **Vorhandene Pumpstationen stärker nutzen:** PSS läuft in Hochlast mit ≈ 0,6 bar, installiert sind ≈ 3,7 bar (2×429 m³/h bei 40 m). Je bar PSS-Gewinn steigt der Δp an Fraunhofer um +0,3 bar; das ist der direkte Hebel für den kritischen Süden
* **Lokale Einspeisung im Süden** (HWS-Fahrweise, ggf. dezentraler Elektrodenkessel/Wärmepumpe): +1 bar je 100 kg/s an Fraunhofer
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

**Bereits geliefert:** ACRON-Stundenwerte 2025, WV640 Bl. 3, WV650, WV660.

| Prio | Information (Nr. der Datenanfrage) | wird gebraucht für |
|---|---|---|
| 1 | **Korrektes GT-Ost-Wärmesignal** (das gelieferte ist eine Kopie der HWW-Sekundärwärme) bzw. vollständiger GT-Durchfluss | Ost-Erzeugung, Kalibrierung (1.8) |
| 1 | Außentemperatur (`Import_Data_stadtbach_15min`) bzw. Freigabe DWD | Auslegungslast (4.1) |
| 1 | Kunden-Δp_min laut TAB bzw. Vertrag; Alarm- oder Beschwerdegrenze (D2, G6) | Kriterium aller A-Aussagen |
| 1 | HKW-Regelung (Schlechtpunkt-Stationen, Sollwerte) und Status der Werte 4,0/7,5 bar (Erfahrungswert oder Grenze) | Machbarkeit (2.2) |
| 1 | Pumpenkennlinien und Δp-/Abschaltgrenzen HKW, Ost, PSS/PSW (A1, A2) | Machbarkeit (2.2, 6) |
| 1 | Regelphilosophie Ost: massenstrom- oder Δp-geführt; Schlechtpunkt-Sollwerte (A3) | Modellstruktur (2.1) |
| 1 | Speicherkonzept und Fläche (C1, C2) | Phase 5 |
| 2 | Minutenwerte an kritischen Stationen und Feldtest-Bereitschaft (E2); Stunden-Min/Max (`acron_stundenwerte_minmax`) | Validierung (3.2/3.3/3.5) |
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
| Speicherwirkung +0,1…0,2 bar | Netzhebel nicht validiert; Struktur (2.3) | **Durch gemessene Hebel gestützt** (lokale Einspeisung wirkt in der City mit +0,07…0,12 bar je 100 kg/s). Hebel am MAN per Feldtest (3.3) bestimmen; als eingesparte Förderhöhe bzw. Aufnahmekapazität ausdrücken; Ensemble | 2, 3, 7 | V |
| Bestand kritisch, Defizit 15–19 bar·h | S-05, Auslegungsfall (2.1) | **Nach Daten widerlegt** (Last 2025: Reserve ≈ 1,3 bar bis 4,0 bar am HKW; alle Mitte-Stationen ≥ 1,1 bar). Bei Auslegungslast mit erforderlicher HKW-Δp P50/P90 neu bewerten; Fraunhofer/Süd gesondert | 1, 2, 4 | A |
| Ausbau nur bis +5…10 % | S-05, S-02, Ausbauort | Anker: Größenordnung +20…40 % bis 4,0 bar am HKW. Exakt über die Aufnahmekapazität je Gebiet, mit Ost-Erzeugern an der Grenze | 2, 4, 6 | A |
| HKW-Limit ab +15 % | Limit = 2025-Beobachtung (2.2) | **Artefakt bestätigt** (HKW-Wärme P99 62 von 127 MW). Plangrenzen und Merit-Order; Ost-Erzeuger sind der eigentliche Engpass | 1, 4 | A |
| Druckanhebung ist der Haupthebel | per Konstruktion (2.2) | Reserve HKW ≈ 0,8 bar (P95 Hochlast), wirkt mit 0,7–0,84 durch; Ost-Pumpen nahe 7,5 bar. Kostenvergleich mit PSS-Nutzung, Booster und Rücklaufabsenkung | 1, 6 | A/V |
| Standort Innenstadt wirkt stärker | Lastverteilung nicht identifizierbar (3.4) | Verbundflüsse über den Tracer (3.5) bestimmen. Für den kritischen Süden sind lokale Einspeisung oder PSS um ein Vielfaches wirksamer als der MAN | 2, 3, 5, 7 | V |
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
| Stundenwerte zu grob für Spitzen-Δp und Tracer (Laufzeiten 1–2 h) | Stunden-Min/Max (`acron_stundenwerte_minmax`), 15-min- oder Minutenwerte nutzen |
| Weitere Signalfehler wie beim GT-Signal | Duplikat- und Bilanzprüfung aller Signale als feste Prüfroutine in Phase 1 (Kopien, Hängewerte wie `PSW_Durchfluss_RL_nach_Mitte` = 1078, Einheitentest) |
| Kosten fehlen | technische Rangfolge mit Machbarkeit berichten; Kostenrangfolge als offener Punkt |
