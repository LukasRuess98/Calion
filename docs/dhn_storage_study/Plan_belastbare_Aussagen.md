# Plan: Von der Studie zu belastbaren Aussagen – Großwärmespeicher Standort S, Netz DHN-A

> **Anonymisierung:** Netz „DHN-A“. Verbraucher V01–V24; die Zuordnung zu den Klarnamen liegt nur lokal beim Auftraggeber. Erzeuger nach Typ:
> * KWK = Gas-KWK-Hauptanlage und Druckhalter
> * MVA = Abfallverbrennung
> * GT = Gasturbine
> * Bio-KWK = Biomasse-KWK
> * HW1/HW2 = Heizwerke; HW2 mit Wärmeübertrager zum Sekundärnetz West
> * PS1/PS2 = Pumpstationen
>
> Weitere Bezeichnungen: Speicherstandort **S = Verbraucher V22**; L1–L7 = Haupt- und Transportleitungen; N_… = Modellknoten; A1… = Armaturen; Plan A/B/C = Betreiberpläne (Erzeuger, Netz Mitte, Netz West). Datensatz und Spaltennamen: `data/dhn_a/README.md`.

Stand: 2026-10-01, **Version 2 nach Prüfung mit den Messdaten 2025 und den Plänen Plan A/650/660** · Bezug: `Review_Speicherstudie.md` (Befunde 2.1–3.6, Datenprüfung Abschnitt 9) und Notebook Studien-Notebook (Branch Studien-Branch, Stand `121196e`). Der Plan ersetzt den Plan aus Kap. 23.1 der Studie (Phasen A–E) und schärft ihn.

**Hinweis zur Weitergabe:** Der Plan enthält aggregierte, aus NDA-Daten abgeleitete Kennzahlen. Vor externer Weitergabe freigeben lassen.

**Was sich mit den Daten geändert hat (Kurzfassung):**
* Die Review-Befunde sind bestätigt.
* Die Daten liefern bereits **Validierungsziele** (gemessene Netzhebel, Temperatur-Tracer, Regelkennlinie des KWK) und einen **Plausibilitätsanker** für die Kernfrage.
* Sie zeigen einen **Signalfehler** (GT-Wärme), der vor jeder Neukalibrierung behoben sein muss.
* Der Schwerpunkt verschiebt sich: Bei Last 2025 ist der Bestand **nicht kritisch**. Bei **Auslegungslast** (−14 °C, n−1, Wetterdaten DWD Referenzstation und Lastgänge 2020–2022) ist er **knapp ausreichend**, sofern sich das Westnetz wie in Plan A aus seinen Kesseln versorgt.
  * Die erforderliche KWK-Δp liegt dann bei ≈ 3,2–3,6 bar; maßgebend ist bei P90 der Süden.
  * Dem stehen 4,0 bar (statische Worst-Case-Simulation des Betreibers) bzw. ≈ 5,7 bar (Pumpe) gegenüber (`Datenanalyse_Auslegung.md`).
  * Bezieht das Westnetz wie 2025 Wärme aus dem Verbund, sind es 3,9–4,5 bar.
* **Die Hydraulik begrenzt an kalten Tagen**, weil die Ost-Erzeuger ≈ 1:1 an die KWK-Δp gekoppelt sind und an ihrem Δp-Erfahrungswert laufen. Die wirksame KWK-Grenze liegt heute bei ≈ 3,6–4,3 bar.
* Die thermische Lücke am Auslegungstag ist im Plan-A-Fall klein: 30–60 MWh, nur bei P90 und n−1. Bei West-Bezug wie 2025 wären es 80–230 MWh.
* **Die KWK regelt auf V06 am Südende der Stammleitung L4.** Eine Einspeisung auf der Ostseite, wo der Speicherstandort S liegt, wirkt dort kaum (+0,03 bar je 100 kg/s, im Süden +0,85). Der Speicher am Standort S senkt die KWK-Δp deshalb nur um ≈ 0,08 bar.
* Stand gegen das Ziel: Abschnitt 1.6.

---

## 1. Was heißt „richtige Aussage“?

### 1.1 Drei Aussagetypen mit eigenen Nachweisanforderungen

| Typ | Beispiel | Nachweis, bevor die Aussage in den Bericht darf |
|---|---|---|
| **P – Physik** | „Entladen ist ohne Pumpe hydraulisch unmöglich“ | Herleitung und Test. *Schon erfüllt.* |
| **V – Wirkung/Vergleich** | „Der Speicher am V22 hebt den kleinsten Kunden-Δp um x bar“, „Standort A wirkt stärker als B“, „Maßnahme M1 vor M2“ | (1) physikalisch konsistentes Modell (Massenbilanz je Erzeuger, eine Druckhaltung); (2) **Wirkung an realen Ereignissen validiert** (Abschnitt 4, Phase 3.2); (3) Aussage gilt in ≥ 90 % der Unsicherheitsläufe **und** in allen plausiblen Modellvarianten |
| **A – Absolut/Machbarkeit** | „Der Bestand erfüllt Δp_min bei −14 °C“, „Ausbau bis +x % möglich“, „Auslegungsdruck y bar“ | zusätzlich zu V: (4) Grenzwerte und Erzeugergrenzen vom Betreiber bestätigt; (5) Δp an den kritischen Stationen bei Hochlast validiert (RMSE ≤ 0,2 bar, Bias ≤ 0,1 bar); (6) Auslegungslast als Band; Angabe als P50/P90 |

Erfüllt eine Aussage die Kriterien nicht, wird sie **bedingt** formuliert: „Unter der Annahme …, gilt …“. Alternativ entfällt sie.

### 1.2 Fragestellung umdrehen: erforderliche Förderhöhe statt „Defizit bei festgehaltenem Druck“

Die Studie hält die Erzeugerdrücke fest (und verschlechtert sie pauschal um 0,65 bar) und misst dann ein „Δp-Defizit“. Damit hängt das Ergebnis an einer willkürlichen Annahme. Außerdem ist die Druckanhebung damit per Konstruktion die beste Maßnahme (Review 2.1/2.2).

**Richtig ist die Frage, wie der Betrieb sie stellt:**
* **Erforderliche Erzeuger-Förderhöhe:** Welche Druckdifferenz muss das KWK fahren, und welche Förderhöhen brauchen die Ost-Pumpen, damit **alle** Kunden am Schlechtpunkt Δp_min erhalten? Das wird mit dem **Verfügbaren** verglichen: Pumpenkennlinie, max. Δp am Werksaustritt (KWK 4,0 bar, Ost 7,5 bar laut Plan A), Abschaltdrücke, PN.
* **Aufnahmekapazität:** Wie viel zusätzliche Last (MW) ist je Gebiet bei verfügbarer Förderhöhe möglich?
* **Wirkung jeder Maßnahme**, auch des Speichers: eingesparte Förderhöhe [bar] und zusätzliche Aufnahmekapazität [MW] je Gebiet, später in €/MW.

Damit entfällt S-05 als Annahme. Die Druckanhebung wird nicht mehr als Wirkung bewertet, sondern als **Machbarkeitsfrage** gegen Pumpenkennlinien und Grenzen.

**Die Daten stützen diese Umstellung** (Review 9.2, N3): Das KWK fährt seine Δp lastabhängig von ≈ 1,8 auf ≈ 2,9 bar hoch, während die Kunden-Δp in der Mitte über alle Lastbereiche bei ≈ 1,6–1,8 bar (P10 1,2–1,5) bleiben. Der Betrieb hält also den Kunden-Δp und lässt die Erzeugerdrücke frei. Genau das bildet die Frage „erforderliche Förderhöhe“ ab.

### 1.4 Was die Daten heute schon zeigen (Review Abschnitt 9)

| Befund aus den Daten | Bedeutung für den Plan |
|---|---|
| `gas_turbine_heat` ist eine Kopie von `boiler_plant_2_secondary_heat` | vor jeder Rechnung beheben (1.8): GT-Einspeisung, Ost-Erzeugung und Last sind sonst falsch |
| Die KWK ist laut Plan A/Plan B einziger Druckhalter; MVA, GT und HW1 nur im Not- bzw. Inselbetrieb | Struktur 2.1 (KWK als Slack) ist **durch die Pläne vorgegeben**, keine Variante mehr |
| S-05 empirisch: KWK-Δp-P5 nur −0,18 bar, MVA −0,33 bar unter dem Basistag; die angenommene Kombination trat nie auf | S-05 entfällt (1.2) |
| Basistag 14.02.: f_m = 0,86; 215 MW nicht reproduzierbar (≈ 169 MW nach Studiendefinition) | Basistag und Auslegungslast neu ableiten (1.3, 1.11) |
| KWK-Δp 2025 in Hochlast P95 3,2–3,5 bar → Reserve ≈ 0,5–0,8 bar bis 4,0 bar; KWK-Wärme P99 62 von 127 MW | KWK hat Leistungs- und Druckreserve. Wegen der Ost-Kopplung ist sie aber nur bis ≈ 3,6–4,3 bar nutzbar |
| **Ost-Kopplung:** Δp_MVA − Δp_KWK = 0,56 + 0,301·(ṁ_Ost/100)² − 0,214·(ṁ_KWK/100)² (R² 0,86); Durchgriff 0,8–1,0 bar je bar KWK-Δp | Validierungsziel (3.4). Die Δp-Grenzen von KWK und MVA sind **gemeinsam** zu prüfen. Ost-Vorlauf 120 °C statt 114 °C entspricht ≈ +0,8 bar wirksamer KWK-Grenze |
| **Schlechtpunktregelung:** Die KWK regelt auf **V06** (Südende L4, ≈ 1,2 bar), das Heizwerk West auf V01/V13 (Leitungsenden W1). Regelgesetz Δp_KWK = 2,05 + 0,223·F² − 1,03·ṁ_HW1/100 − 0,42·Δp_PS1 (R² 0,65) | Der Süden ist bei hoher Last die maßgebende Anforderung (Anker 3.6) |
| **Einspeise-Hebel** (anstelle von KWK-Wasser): am Regelpunkt V06 +0,85 bar je 100 kg/s im Süden, +0,03 bar im Osten; City +0,16 bar je 100 kg/s im Osten | Validierungsziel 3.2; Speicher am Standort S hydraulisch ≈ 0,08 bar KWK-Entlastung |
| Lastabflachung unter ≈ −5 °C: 2020–2022 −10…−15 % gegen den unbegrenzten Bedarf, kein Ferieneffekt. 2025 Kunden voll versorgt, der Verbund über HW2-Kessel West entlastet (−8 MW) | Auslegung auf den **unbegrenzten** Bedarf (4.1) |
| MVA, Bio-KWK und HW1 lagen 2025 an ihren Planleistungen; MVA-Δp in 390–550 h über 7,5 bar | Ausbaulast muss vom KWK kommen; Ost-Förderhöhe ist knapp, und 7,5 bar ist keine harte Grenze → klären (A2) |
| Durchfluss in t/h (Kundenstationen: Abweichung 0,1–0,3 %), SL-Messung im Rücklauf (Plan B) | Massenströme ≈ 4–5 % höher ansetzen (1.9) |
| V06 (Süd) ist die kritischste Station (P1 0,9 bar) und wird nicht genutzt; HW2-Prim < 1,0 bar in 276 h | DiffDruck-Stationen einbeziehen (1.10); Δp_min je Knoten (TAB; HW2 0,7 bar) |
| Gemessene Netzhebel (Tabelle in 3.2) | **Validierungsziele** für jedes Modell (3.2) |
| Temperatur-Tracer: Ost-Wasseranteil V22 ≈ 75 %, V23 ≈ 49 %, City (V17) ≈ 28 % | Validierungsziel für die Verbundflüsse und die Lastverteilung (3.5) |
| Anker (`Datenanalyse_Auslegung.md`, Abschnitt 6): erforderliche KWK-Δp bei **Auslegungslast** (−14 °C, n−1, Rücklauf gemessen 59 °C, West aus eigenen Kesseln) ≈ **3,2–3,6 bar** als Maximum aus Mitte (1,0 bar) und Süd-Regelung. Ausbaureserve bis 4,0 bar +5…13 %, bis 5,7 bar +24…34 %. Mit West-Bezug wie 2025: 3,9–4,5 bar | Modell muss diesen Anker reproduzieren (3.6). F1 lautet „knapp ausreichend“. Entscheidend sind die West-Fahrweise, die Grenze hinter 4,0 bar und der Rücklauf |
| Erzeugungsleistung Verbund (Plan A, −14 °C, n−1) 251 MW gegen 235–252 MW Stundenspitze (West aus eigenen Kesseln): Lücke nur bei P90, 30–60 MWh. Bei West-Bezug wie 2025: 80–230 MWh | Thermischer Speichernutzen ist eine n−1-Reserve, nicht der Hauptnutzen (Phase 5) |
| Anschlussleistung je Teilgebiet (`sectors.csv`): City 25 %, Süd 19 %, Mitte-L3 15 %, Mitte-L2 13 %, Ost-L5 11 % (Standort S 32 MW), Mitte-L4 10 % | Lastverteilungsschlüssel für das Netzmodell (2.4) |

### 1.5 Stand der Umsetzung (2026-10-01)

| Arbeitspaket | Stand |
|---|---|
| 1.8 GT-Signal | **erledigt** in `scripts/dhn_study/daten.py` (`erzeugung`: gemessen 35 %, Stillstand 27 %, imputiert 38 %, R² 0,76); im Notebook noch zu übernehmen |
| 1.9 Einheit t/h | **geprüft** (`daten.einheitentest`); im Notebook noch umzustellen |
| 1.10 DiffDruck-Stationen | **erledigt** für die Datenanalyse (`daten.kunden_dp`); im Notebook noch einzubauen |
| 1.11 Basistag | geprüft: 14.02. ≈ 169 MW (nicht 215). Der Auslegungsfall wird stattdessen aus dem Lastband abgeleitet (4.1) |
| 4.1 Auslegungslast | **erledigt** (`Datenanalyse_Auslegung.md`, Abschnitt 4): −14 °C ≈ 10-Jahres-Kältetag Referenzstation (DWD). Verbund-Stundenlast **235–252 MW unbegrenzt** (Fit auf Tage ≥ 0 °C), mit Westnetz aus eigenen Kesseln (Plan A). Bei West-Bezug wie 2025 262–280 MW; 213–229 MW entsprechen der heute begrenzten Lieferung. Spreizung aus gemessenem Rücklauf 120/59 °C, Auslegungswoche 5-Tage-Mittel ≈ −11 °C |
| 1.4 Erzeugergrenzen | **als Band** (`hydraulik`): KWK 4,0 bar (Erfahrungswert laut Plan A), 4,16 bar (max. 2025), ≈ 5,7 bar (Pumpe); MVA 7,5 bar (Erfahrungswert), 8,2 bar (P99 2025). Kopplung über das Ost-Gesetz; Erzeugungsleistung nach Plan A (n−1) |
| 2.4 Lastverteilung | **Daten vorhanden:** Anschlussleistung und Netzvolumen je Teilgebiet (`data/dhn_a/sectors.csv`, 52 Teilgebiete) |
| Hydraulische Begrenzung | **analysiert** (`Datenanalyse_Auslegung.md`, Abschnitt 5): Süd-Schlechtpunkt auf Sollwert, Ost-Pumpen an der Grenze, Ausweichen über HW1 und HW2 West |
| Regelpunkte | **bestimmt** (Abschnitt 5.6, `hydraulik.regelpunkt_signatur`, Abbildungen): Verbund V06, West V01/V13; V01 dem Westnetz zugeordnet (Korrektur) |
| 3.2 / 3.4 / 3.5 / 3.6 | Validierungsziele **berechnet**: Netzhebel und Einspeise-Hebel, Ost-Kopplung, Tracer, Mitte-Verlustgesetz und Süd-Regelgesetz. Abgleich mit dem Modell folgt in Phase 2/3 |
| 1.7 Modul + Tests | **begonnen**: `scripts/dhn_study/` (`daten`, `wetter`, `auslegung`, `anker`, `hydraulik`, `abbildungen`) mit 20 Tests (`tests/test_dhn_study.py`); Netzlöser noch im Notebook |

### 1.6 Stand gegen das Ziel (Gesamtprüfung 2026-10-01)

Ziel des Plans: Aus der Studie belastbare Aussagen zu den Leitfragen F1–F5 (Abschnitt 2) gewinnen, je mit dem Nachweis ihres Aussagetyps (1.1).

| Leitfrage | Aussage heute | Typ / Nachweis | Was bis zum Ziel fehlt |
|---|---|---|---|
| **F1** Reicht das Netz bei Auslegungslast? | **Ja, knapp:** erforderliche KWK-Δp 3,2–3,6 bar gegen 4,0 bar (Worst Case des Betreibers) bzw. ≈ 5,7 bar (Pumpe). Referenzfall: −14 °C, n−1, unbegrenzter Bedarf, West aus eigenen Kesseln | **A bedingt.** Erfüllt: Grenzwerte vom Betreiber (4), Lastband P50/P90 (6). Unabhängiger Abgleich mit der Worst-Case-Simulation des Betreibers stimmt auf 0,4–0,8 bar. Fehlt: konsistentes Netzmodell (1) und dessen Δp-Validierung (5); bisher Ersatzgesetze mit 1,2- bis 1,3-facher Extrapolation | Netzmodell Phase 2/3 muss den Anker reproduzieren |
| **F2** Wie viel Ausbau, wo? | Gesamt +5…13 % bis 4,0 bar, +24…34 % bis zur Pumpengrenze; regional noch offen | A bedingt, wie F1 | Aufnahmekapazität je Gebiet mit Netzmodell und `sectors.csv` (4.3) |
| **F3** Was bringt der Speicher am Standort S gegenüber Alternativen? | **Hydraulisch wenig:** ≈ 0,08 bar (0,04–0,11) KWK-Entlastung, weil S auf der Ostseite liegt und der Regelpunkt V06 im Süden. Einspeisung im Süden wirkt ≈ 30-mal stärker. **Thermisch:** n−1-Reserve für die P90-Spitze, 30–60 MWh | **V gestützt** durch natürliche Experimente (Einspeise-Hebel, n ≈ 7 700 h) und Tracer. Fehlt: direkter Hebel am Standort S (Feldtest 3.3 oder validiertes Modell), Unsicherheitsläufe (3) | Feldtest oder Modell mit Speicher am Standort S; Vergleich mit Süd-Varianten |
| **F4** Speicherkonzept und Auslegungsdruck | Vorlaufdruck am Standort S 11,6–12,8 bar bei Auslegung, bis ≈ 14 bar an der Pumpengrenze; 2025 max. 12,0 bar | Eingangsgröße datenbasiert; Konzept offen | Phase 5 mit Planer: Konzepte K1–K4, Absicherung, Druckstoß |
| **F5** Günstigste Maßnahme(n) | Wirkungen quantifiziert: Süd-Einspeisung/HW1 0,85 bar je 100 kg/s am Regelpunkt, Rücklauf −5 K ≈ −0,3 bar, Ost-Vorlauf über der Heizkurve ≈ +0,8 bar wirksame Grenze, Speicher am Standort S ≈ 0,08 bar | V (Wirkung), ohne Kosten | Kostenansätze (F1/F2 der Datenanfrage), Maßnahmenvergleich Phase 6 |

**Gesamturteil:**
* **Inhaltlich ist die Kernfrage beantwortet.** Das Netz reicht bei Auslegung knapp. Der Speicher am Standort S ist hydraulisch kein wirksames Mittel für den Engpass, der im Süden liegt; sein Nutzen ist thermisch und betrieblich.
* Diese Richtung ist datenbasiert und unabhängig vom Modell der Studie belegt.
* **Formal am Ziel sind wir noch nicht.** Für A-Aussagen im Bericht fehlen das konsistente Netzmodell (Phase 2), seine Validierung (Phase 3) sowie Planer- und Kostenbeiträge (Phasen 5/6).
* Die Korrekturen am Notebook der Studie (Phase 1, 1.1–1.6) sind noch nicht umgesetzt; die Datenanalyse läuft unabhängig davon in `scripts/dhn_study/`.

### 1.3 Aussagenregister
Jede Aussage im Bericht bekommt einen Eintrag: Typ (P/V/A), Beleg (Zelle, Datei, Kennzahl), tragende Annahmen, Validierungsnachweis, Unsicherheitsband und Status. Der Bericht wird **aus** dem Register erzeugt, nicht umgekehrt. Ziel für die heutigen Kernaussagen siehe Abschnitt 6.

---

## 2. Phase 0 – Bewertungsrahmen festlegen (Woche 0–1, mit Auftraggeber)

Vor jeder weiteren Rechnung wird schriftlich vereinbart (2 Seiten, Freigabe durch den Auftraggeber = **Gate G0**):

| Punkt | Festzulegen |
|---|---|
| Leitfragen | F1: Reicht das Netz heute bei Auslegungslast mit den vorhandenen Pumpenreserven? F2: Wie viel Ausbau ist wo ohne Maßnahmen möglich? F3: Was bringt der Speicher am V22 im Vergleich zu Alternativen? F4: Welches Speicherkonzept und welcher Auslegungsdruck? F5: Welche Maßnahme(nkombination) ist je Ausbaupfad am günstigsten? |
| Auslegungsfall | Auslegungs-Außentemperatur (−14 °C?), **Auslegungstag und Auslegungswoche** (Kältewelle 3–5 Tage), Heizkurve im Betrieb |
| Grenzwerte | Kunden-Δp_min aus den TAB der Betreiber (HW2-WÜ: 0,7 bar laut Plan), Siedeabstand, PN, Abschaltdrücke, Erzeugergrenzen |
| Ausbaupfade | konkrete Vorhaben (D1); andernfalls wird die Aufnahmekapazität je Gebiet berichtet |
| Speicherkonzepte | welche Varianten (Phase 5) überhaupt in Frage kommen (Fläche, Bauhöhe, Druckhaltung) |
| Maßnahmenkatalog | inkl. der in der Studie fehlenden Optionen Druckerhöhungsstation und Rücklauftemperaturabsenkung (Phase 6) |
| Kostenbasis | wer Kostenansätze liefert (F1/F2) |
| **Rückfragen aus der Datenprüfung** | (1) Korrektes GT-Wärmesignal (das gelieferte ist eine Kopie der HW2-Sekundärwärme). (2) Ist 4,0 bar am KWK-Austritt eine harte Grenze oder ein Erfahrungswert (Fußnote Plan A)? Warum lag die MVA-Δp in 390–550 h über 7,5 bar? (3) Auslegungs-Vorlauftemperatur am KWK: 107 °C laut Plan A („127 MW bei 107–60 °C“) oder 120 °C laut Vorgabe? (4) Gilt der Auslegungsfall als n−1 („bei Ausfall der größten Erzeugungsleistung“)? (5) Regelung des KWK: Schlechtpunkt- oder Kennlinienregelung, auf welche Stationen? *Stand: (2) Erfahrungswert aus statischer Worst-Case-Simulation; (3) 120 °C laut Heizkurve (Datenanalyse, Abschnitt 3); (4) ja, n−1; (5) Schlechtpunktregelung auf V06 (aus Daten, Abschnitt 5.6); (1) offen, GT-Wärme bis dahin imputiert.* |

Parallel geht die **Datenanfrage** an den Betreiber, reduziert auf das Entscheidende (Abschnitt 5).

---

## 3. Phase 1 – Sofortkorrekturen ohne Betreiberdaten (Woche 1–2)

| Nr. | Arbeitspaket | Ergebnis / Akzeptanz |
|---|---|---|
| 1.1 | Diagnose-Checks aus Review 6.1 ausführen: Massenbilanz je Erzeuger (VL gegen RL), minimale Druckrand-Einspeisung. *S-05, f_m und KWK-Δp gegen 4,0 bar sind bereits aus den Daten geprüft (Review 9.1).* | Ergebnistabelle |
| 1.2 | **S-05 als Annahme streichen.** Nur noch als datenbasierte Sensitivität führen: KWK −0,18 bar, MVA −0,33 bar Δp (P5 Hochlast gegen Basistag) | S1 = Basistag skaliert, ohne Abschlag |
| 1.3 | **Auslegungslast explizit:** `heat_factor` aus einer Regression auf **Tagesmittel** (T_a, Wochentag, Vortagstemperatur) statt Stundenwerten; Band P50/P90; f_m ausgeben | `LAST_MODELL` wird tatsächlich verwendet |
| 1.4 | **Erzeugergrenzen aus Plan A:** Massenströme/Leistungen bei AT −14 °C, Δp am Werksaustritt (4,0/7,5 bar), VL-/RL-Abschaltdrücke als Nebenbedingungen in `evaluate` | keine Limits mehr aus 2025-P99,9 |
| 1.5 | Speicher-Auslegungsdruck korrekt ableiten (Review 6.4); Textfehler Antwort 15; Antworten 3, 4, 13, 18, 23 und Summary nach Aussagetyp umformulieren | „Stand 1“ des Berichts |
| 1.6 | Kalibrierung: nicht konvergierte Stunden bestrafen statt Residuum 0 setzen; Kap.-13-Text an den Code angleichen | Anteil Nichtkonvergenz ausgewiesen |
| 1.7 | **Code aus dem Notebook in ein Modul überführen** (z. B. `scripts/dhn_study/`) mit Unit-Tests: Analytik (Parallelrohr, Ring), Massenbilanz je Erzeuger, Verschiebungsinvarianz (gleiche Randverschiebung ⇒ gleiche Knotenverschiebung), Speicherbilanz. Tests laufen mit einem **synthetischen** DHN-A-ähnlichen Datensatz, damit sie ohne NDA-Daten in CI laufen | Notebook ruft nur noch das Modul auf. Grundlage für alle weiteren Phasen |
| 1.8 | **GT-Signal korrigieren:** `gas_turbine_heat` verwerfen (Kopie von HW2-Sek). GT-Wärme und -Massenstrom aus `gas_turbine_flow`·Δh (35 % Abdeckung). Stillstand bei T_VL < 60 °C ⇒ 0. Übrige Stunden als fehlend markieren, beim Betreiber das richtige Signal anfordern. Folgerechnungen neu: Ost-Erzeugung, Restlast R, Gesamterzeugung, Lastregression | Prüfsumme: Ost-Erzeugung im Wintermedian ≈ 88 MW statt 77 MW |
| 1.9 | **Einheit t/h** für alle Kunden- und SL-Durchflüsse (Bio-KWK: m³/h im VL). Dichte am Messort; die SL-Messung liegt im Rücklauf (Plan B) | Einheitentest je Station ≈ 1,00 |
| 1.10 | **DiffDruck-Stationen einbeziehen:** V06, V03, V10, V07, V19. Δp-Residuen direkt aus `DiffDruck` statt nur aus VL − RL | V06 als kritischer Süd-Knoten in Kalibrierung, Bias und Kriterium |
| 1.11 | **Basistag neu wählen:** nach korrigierter Erzeugung unter den vollständig gemessenen Tagen (Kandidaten 17.–19.02., 31.12.2025). Das Tagesmittel dokumentieren | 215-MW-Angabe ersetzt |
| 1.12 | **Δp_min je Knoten** aus der TAB; HW2 0,7 bar (Plan A). Bis zur TAB-Klärung als Band 0,8–1,2 bar | Kriterium knotenweise statt pauschal |

**Mögliche Aussagen nach Gate G1 (Ende Woche 2):**
* P-Aussagen und korrigierte V-Aussagen mit ausdrücklicher Bedingung.
* Zusätzlich **datengestützte Aussagen zum Ist-Zustand 2025**: Druckreserve am KWK, V06 als kritische Station, Ost-Erzeuger an der Grenze, gemessene Netzhebel.
* Noch keine Aussagen zum Auslegungsfall.

---

## 4. Phasen 2–8

### Phase 2 – Konsistente Modellstruktur (Woche 2–6)

**2.1 Eine Druckhaltung, Massenbilanz je Erzeuger**

Formulierung je Stunde mit gleicher Einspeisung s im VL und −s im RL:

* KWK ist der einzige Druckrand: RL-Druckhöhe = Druckhaltung (Ruhedruck), VL-Druckhöhe = RL + Δp_KWK. KWK ist der **Slack**: Seine Einspeisung schließt die Bilanz und ist damit automatisch in VL und RL gleich. **Durch die Pläne bestätigt:** Plan A „Ruhedruckanbindung auf P-Saugseite“ (KWK), MVA „Ruhedruck (Notbetrieb)“, GT und HW1 „(Inselbetrieb)“; Plan B „RL-Absperrarmatur muss zur Sicherstellung der Druckhaltung offen bleiben“.
* Ost-Erzeuger und HW1 speisen höchstens ihre Planleistung ein; 2025 lagen sie bereits an der Grenze (MVA 46 MW, Bio-KWK 15,4 MW, HW1 569 t/h). Zusatzlast geht damit an das KWK.
* Ost-Erzeuger, zwei Varianten. Phase 3 entscheidet anhand der Daten, welche die gemessenen MVA-Drücke besser trifft; der Betreiber bestätigt das (A3).
  * **(a) massenstromgeführt:** MVA, GT, Bio-KWK, HW1 speisen den gemessenen bzw. aus Q/ΔT abgeleiteten Massenstrom ein. Ihre **erforderliche Förderhöhe** H_VL − H_RL am Erzeugerknoten ist Ergebnis und wird gegen 7,5 bar bzw. die Pumpenkennlinie geprüft.
  * **(b) Δp-geregelt:** Der Massenstrom der MVA wird je Stunde per 1-D-Nullstellensuche so bestimmt, dass H_VL − H_RL am MVA-Knoten dem gemessenen Wert entspricht. Er gilt in VL und RL gleichermaßen.
* Die gemessenen MVA- und Ost-Drücke werden damit **Validierungsziele** statt Randbedingungen. Die Offsets MVA_REF_VL/RL (−0,3/+7,7 m) entfallen.

Umsetzung mit dem vorhandenen Löser (geringer Aufwand). `solve_case(cfg=dict(ava_ref=False))` existiert bereits; statt `inj[MVA] = 0` wird der Massenstrom eingesetzt:
```python
CASE_COLS += ["m_ava"]                                   # MVA-Massenstrom in die Fälle übernehmen
# in solve_case, Zweig ava_ref=False:  inj[:, nidx["MVA"]] = cs.m_ava.values   (statt 0.0)
def solve_consistent(cs, dp_kwk_bar, m_stor=None, cfg=None):
    cs = cs.copy(); cs["pVL_kwk"] = cs.pRL_kwk + dp_kwk_bar      # VL am KWK = Druckhaltung + Δp-Sollwert
    return solve_case(cs, cfg=dict(cfg or {}, ava_ref=False), m_stor=m_stor)
```

**2.2 Schlechtpunktregelung als Szenariomodus**

Mit nur einem Druckrand und festen Lasten verschiebt eine Änderung von Δp_KWK **alle** VL-Druckhöhen gleichmäßig. Die erforderliche KWK-Druckdifferenz je Stunde ergibt sich deshalb ohne Iteration:
```python
res = solve_consistent(cs, dp0); dpk = kunden_dp(res)                       # Kunden-Δp inkl. Sektionsabschlag (2.3)
dp_kwk_erf = dp0 + (DP_MIN[None, :] - dpk).max(axis=1)                     # erforderliche KWK-Δp je Stunde (< dp0: Reserve)
# Ost-Förderhöhen verschieben sich um denselben Betrag → gegen 7,5 bar / Kennlinie prüfen
```
Im getrennten Betrieb (S7) hat die Ost-Insel keinen KWK-Bezug. Dort wird die MVA zum Druckhalter der Insel; dasselbe Verfahren gilt je Insel.

Die Daten zeigen, dass die KWK-Δp nur mit dem Faktor 0,70–0,84 auf die Kunden durchwirkt (Review 9.2, N4), weil die Ost-Erzeuger mitregeln. In Variante (b) aus 2.1 ist die Verschiebung daher nicht mehr exakt gleichmäßig. Dann gilt: 1-D-Nullstellensuche auf Δp_KWK statt der geschlossenen Formel.

Kennzahlen je Szenario:
* max. erforderliche KWK-Δp gegen 4,0 bar bzw. die Kennlinie,
* max. erforderliche Ost-Förderhöhe gegen 7,5 bar,
* Druckniveau gegen PN und Abschaltdrücke (MVA RL < 5,0 bar, HW1 RL < 4,0 bzw. > 12,0 bar, PS1/PS2 Saugseite < 5,0 bar; jeweils mit dem Bezugsniveau aus Plan A),
* Ruhedruck am KWK gegen den Mindest-Ruhedruck je Netzbereich aus Plan B (City 6,5 bar bei 120 °C),
* Reserve in bar.

Damit sind F1 und F2 direkt beantwortbar.

**2.3 Lastabhängiger Druckabfall innerhalb der Sektionen**

Die konstante Bias-Korrektur (M-11) wurde bei Last 2025 kalibriert. Bei Auslegungslast und Ausbau wächst der sektionsinterne Druckabfall quadratisch; die konstante Korrektur ist dann **nicht konservativ**. Ersatz:

Δp_Kunde,s = Δp_Knoten,s − c_s · (ṁ_s/ṁ_s,ref)^n, mit n ≈ 1,8–2.

c_s wird je Sektion aus den Messstationen gefittet (V03, V24, V10 → N_City; V12 → N_L4; **V06**, V05, V14 → N_Süd; V19, V15 → N_L3; V07 → N_L7). Sektionen ohne Station erhalten ein Band aus vergleichbaren Sektionen.

Die Daten bestätigen die Lastabhängigkeit: Die Differenz KWK-Δp minus ungünstigste Mitte-Station steigt von ≈ 0,2 bar (Schwachlast) auf ≈ 1,0 bar (Hochlast).

**2.4 Lastverteilung**
* Die Energiebilanz 2025 zeigt das Problem (Review 9.1): Ost erzeugt im Winter ≈ 89 MW, nur ≈ 4 MW davon fließen über L1/L3 ins KWK; L2 liefert nur 25 MW für 151 MW Anschluss. Entweder ist die City sehr schwach ausgelastet (0,16), oder **≈ 30–45 MW fließen über die Verbundkanten** in die City. Der Temperatur-Tracer spricht für Letzteres.
* Lastanteile mit plausiblen Auslastungsbändern begrenzen (z. B. 0,3–0,7 der Anschlussleistung im Wintermedian, Industrie separat). V22 (32 MW Anschluss, ≈ 5 MW Wintermedian) dabei gesondert führen.
* Zeitvariable Anteile für Industrie- und Wohnlast.
* Die 17 geschätzten Kundenreihen aus `combined` als Prior nutzen.
* Mindestens drei Lastvarianten als Strukturensemble mitführen.

**2.5 Höhen**
* Geländehöhen aller Knoten und Stationen aus dem **DGM1 (OpenData der Landesvermessung; Verfügbarkeit und Lizenz prüfen)**.
* Mit den aus Schwachlast abgeleiteten Höhen vergleichen. Schwachlastfilter zusätzlich mit kleinem |L1|-Fluss.
* Hochpunkte für die Siedesicherheit bestimmen.

**2.6 Einheiten und Dichte:** erledigt durch 1.9 (t/h; Messort Rücklauf). Nur noch Bio-KWK in m³/h im VL.

**2.7 Strukturell unabhängige Gegenrechnung:** pandapipes als **geschlossener Kreis**, also VL und RL in einem Netz mit Wärmeverbrauchern, einer Umwälzpumpe mit Druckhaltung am KWK und massenstromgeführten Pumpen an den Ost-Erzeugern. Damit prüft pandapipes die Modellannahmen, nicht nur die Numerik.

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
| 3.2 | **Wirkung (Netzhebel) an natürlichen Experimenten:** Das Modell muss die **gemessenen Hebel** (Tabelle unten) und die **Einspeise-Hebel** am Regelpunkt V06 (Süd +0,85, Ost +0,03 bar je 100 kg/s; `Datenanalyse_Auslegung.md`, Abschnitt 7) reproduzieren. Im Modell gleiche Regression auf die simulierten Stunden anwenden oder die Sensitivitäten direkt bilden (∂Δp_Station/∂ṁ_HW1, ∂/∂Δp_KWK, ∂/∂Δp_MVA, ∂/∂PS1-Gewinn) | Vorzeichen in allen Fällen richtig; Betrag ±30 % bzw. ±0,05 bar. **Ohne diesen Nachweis ist keine Aussage über die Speicherwirkung belastbar** |
| 3.3 | **Feldtest mit dem Betreiber (empfohlen):** Sollwertsprung KWK-Δp ±0,2 bar über 2–3 h; Leistungssprung HW1; Minutenwerte an den kritischen Stationen und an Arm. A1 (E2). Damit lässt sich insbesondere ein Hebel für eine Einspeisung **am V22 bzw. im Osten** bestimmen; der HW1-Hebel deckt nur den Süden ab | wie 3.2, mit geringerem Rauschen |
| 3.4 | Ost-Erzeuger: modellierte gegen gemessene Förderhöhe bzw. Drücke an MVA/GT/Bio-KWK. Validierungsziel ist die **Ost-Kopplung** Δp_MVA − Δp_KWK = 0,56 + 0,301·(ṁ_Ost/100)² − 0,214·(ṁ_KWK/100)² und ein Durchgriff von 0,8–1,0 bar je bar KWK-Δp (`Datenanalyse_Auslegung.md`, Abschnitt 5.2) | entscheidet Variante (a) oder (b) aus 2.1; Modell trifft das Gesetz im Bereich 2025 auf ±0,3 bar |
| 3.5 | **Temperatur-Tracer:** Ost-Wasseranteil an den Stationen in Stunden mit T_Ost ≠ T_KWK. Gemessen: V22 ≈ 75 %, V11 ≈ 85 %, V15 ≈ 64 %, V23 ≈ 49 %, V17 (City) ≈ 28 %. Das Modell berechnet die Mischungsanteile aus seinen Flüssen (Aufwind-Mischung, wie `transport_T`, mit Quellmarkierung). Mit 15-min-Daten deutlich schärfer | Anteile ±15 Prozentpunkte. **Bestimmt die Verbundflüsse und damit die Lastverteilung** (2.4) |
| 3.6 | **Plausibilitätsanker** (`Datenanalyse_Auslegung.md`, Abschnitte 5.3 und 6):<br>• Verlust KWK → ungünstigste Mitte-Station = 0,118 + 0,1405·(P/ΔT)² bar (P = Verbundeinspeisung, ΔT = KWK-Spreizung; R² = 0,76)<br>• Süd-Regelgesetz Δp_KWK = 2,05 + 0,223·F² − 1,03·ṁ_HW1/100 − 0,42·Δp_PS1 | Modell trifft beide Verläufe im Bereich 2025 auf ±0,2 bzw. ±0,3 bar |

**Gemessene Netzhebel 2025** (Regression auf stündliche Differenzen, n ≈ 5 000 h). Angegeben ist die Spanne aus zwei Lastdefinitionen (Review 9.2, N4, und `Datenanalyse_Auslegung.md`, Abschnitt 7, mit korrigierter GT-Last):

| Station | je 100 kg/s HW1 | je bar KWK-Δp | je bar MVA-Δp | je bar PS1-Gewinn |
|---|---|---|---|---|
| V06 (Süd) | +1,01…1,02 | 0,66…0,69 | −0,05…+0,04 | +0,30…0,33 |
| City (V03, V10, V24) | +0,07…0,20 | 0,82…0,84 | 0,03…0,10 | −0,06…−0,12 |
| V12 (L4) | +0,06…0,19 | 0,82…0,84 | 0,03…0,09 | −0,06…−0,13 |
| V23 (L1) | +0,02…0,20 | 0,83…0,84 | 0,02…0,09 | −0,04…−0,12 |
| V22 | +0,04…0,09 | 0,73…0,74 | 0,19…0,22 | −0,04…−0,07 |
| V15 (Mitte-L3) | +0,09…0,11 | 0,72…0,75 | 0,19…0,23 | −0,05…−0,06 |

**Gate G2 (Woche 8):**
* 3.1 und 3.2 erfüllt: V- und A-Aussagen sind für die validierten Bereiche zulässig.
* Nur 3.2 erfüllt: V-Aussagen mit Band zulässig, A-Aussagen nur bedingt.
* 3.2 nicht erfüllt: Messkampagne (3.3) vor weiteren Aussagen zur Speicherwirkung.

### Phase 4 – Auslegungsfall und Szenarien (Woche 6–9)

* **4.1 Auslegungslast:**
  * mit korrigierter Erzeugung (1.8). Die Außentemperatur fehlt in den gelieferten Daten: 15-min-Importdaten nachliefern oder DWD-Referenzstation verwenden,
  * Auslegungsfall nach Plan A als **n−1** („bei Ausfall der größten Erzeugungsleistung“) prüfen,
  * Auslegungs-Vorlauftemperatur am KWK klären (107 °C laut Plan A gegen 120 °C laut Vorgabe; 2025 in Hochlast Median 111,7 °C, nur 42 h ≥ 120 °C),
  * Tagesmittel-Regression,
  * Lastgänge 2020–2022 (Definition klären, D3),
  * historische Kältewellen aus den DWD-Klimadaten (Referenzstation),
  * Plausibilisierung über Anschlussleistung × Gleichzeitigkeit.

  Ergebnis: Auslegungstag **und** Auslegungswoche, jeweils P50/P90.
* **4.2 Betriebsweise:**
  * Heizkurve wie tatsächlich gefahren,
  * Rücklauftemperatur lastabhängig aus Daten regressiert (statt konstant),
  * Erzeugereinsatz nach Merit-Order (MVA must-run, Bio-KWK, GT, KWK als Swing, HW1 Spitze) innerhalb der Plangrenzen.
* **4.3 Ausbau:** Ausbaupfade aus D1; andernfalls Aufnahmekapazität je Gebiet. Diese Kenngröße hängt nicht von unbekannten Vorhaben ab.
* **4.4 Schaltzustände** nach B1 (Betriebsanweisung) statt Annahme S7-1/S7-2.

### Phase 5 – Speicherkonzept (Woche 6–10, mit Auftraggeber und Planer)

| Konzept | Hydraulisches Ersatzmodell | Auslegungsdruck | Pumpen |
|---|---|---|---|
| K1 direkt, mehrere schlanke Druckbehälter auf Netzdruck | Einspeisung/Entnahme am Knoten (wie heute) | ≈ p_VL,max + Strangverluste + Absperrreserve | Entladepumpe |
| K2 druckentkoppelt (Speicher bei niedrigem Druck, ≥ p_sat + Abstand) | Einspeisung/Entnahme, beide Richtungen gepumpt bzw. gedrosselt | niedrig (≈ 3–5 bar Ü) | Lade- **und** Entladepumpe; Variante A entfällt |
| K3 atmosphärisch ≤ 95 °C mit Nacherhitzung oder indirekt | Einspeisung mit begrenzter Temperatur; Nachheizung (z. B. Elektrodenkessel) | atmosphärisch | wie K2 |
| K4 Speicher als Druckhaltung | Druckrand am V22 statt (oder neben) KWK | Netzdruck | – |

Je Konzept wird bestimmt:
* Auslegungsdruck korrekt aus Saugdruck + Absperrhöhe bzw. Sicherheitsventil,
* Platzbedarf, Behälteranzahl,
* **Mehrtagesbetrieb** über die Auslegungswoche (rollierende Optimierung; kann in der Kältewelle nachgeladen werden?),
* später die Druckstoßstudie.

Erst danach folgt die Pumpenauslegung.

### Phase 6 – Maßnahmenvergleich (Woche 9–13)

**6.1 Maßnahmenkatalog** (erweitert um bisher fehlende, oft günstigere Optionen):
* Druckanhebung im Rahmen der Pumpenreserve (KWK 2025: ≈ 0,8 bar bis 4,0 bar; KWK-Pumpen 2×1000 + 2×900 t/h bei 73,5 m); Pumpentausch KWK/Ost
* **Vorhandene Pumpstationen stärker nutzen:** PS1 läuft in Hochlast mit ≈ 0,6 bar, installiert sind ≈ 3,7 bar (2×429 m³/h bei 40 m). Je bar PS1-Gewinn steigt der Δp an V06 um +0,3 bar; das ist der direkte Hebel für den kritischen Süden
* **Lokale Einspeisung im Süden** (HW1-Fahrweise, ggf. dezentraler Elektrodenkessel/Wärmepumpe): +1 bar je 100 kg/s an V06
* **Druckerhöhungsstation (Booster)** im Zulauf des kritischen Gebiets. Das ist das direkte Gegenstück zum „Speicher mit Pumpe“, nur ohne Speicher.
* **Rücklauftemperaturabsenkung**: −5 K bei 120/55 °C ⇒ ≈ −7 % Massenstrom, ≈ −14 % Reibungsverlust im ganzen Netz
* gezielte Leitungsverstärkung an den Engpasskanten aus 2.2
* Erzeugerverlagerung (HW1, dezentrale Power-to-Heat-Anlagen)
* Speicher am V22 bzw. am besten Standort; Kombinationen

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

**Bereits geliefert:** Leitsystem-Stundenwerte 2025, Plan A, Plan B, Plan C.

| Prio | Information (Nr. der Datenanfrage) | wird gebraucht für |
|---|---|---|
| 1 | **Korrektes GT-Wärmesignal** (das gelieferte ist eine Kopie der HW2-Sekundärwärme) bzw. vollständiger GT-Durchfluss | Ost-Erzeugung, Kalibrierung (1.8) |
| 1 | Außentemperatur (15-min-Importdaten) bzw. Freigabe DWD | Auslegungslast (4.1) |
| 1 | Kunden-Δp_min laut TAB bzw. Vertrag; Alarm- oder Beschwerdegrenze (D2, G6) | Kriterium aller A-Aussagen |
| – | *Geklärt:* Westnetz bei Auslegung aus eigenen Kesseln (Auftraggeber); 4,0 bar aus Erfahrung und statischer Worst-Case-Simulation (Betreiber); Regelpunkte V06 bzw. V01/V13 (aus Daten, Abschnitt 5.6) | – |
| 2 | Mindest-Δp an V06 laut TAB; Pumpenkennlinien KWK und MVA (nur für Ausbau über +5…13 %) | Reserve, Ausbau (4.3) |
| 2 | Kann Ost im heutigen Kältebetrieb über der Heizkurve fahren (Betriebshebel)? *Geklärt: n−1 und Erfahrungswerte (Plan A), Unterversorgung bei Kälte (Auftraggeber)* | Maßnahmen (6) |
| 1 | Pumpenkennlinien und Δp-/Abschaltgrenzen KWK, Ost, PS1/PS2 (A1, A2) | Machbarkeit (2.2, 6) |
| 1 | Regelphilosophie Ost: massenstrom- oder Δp-geführt; Schlechtpunkt-Sollwerte (A3) | Modellstruktur (2.1) |
| 1 | Speicherkonzept und Fläche (C1, C2) | Phase 5 |
| 2 | Minutenwerte an kritischen Stationen und Feldtest-Bereitschaft (E2); Stunden-Min/Max (Stunden-Min/Max-Export) | Validierung (3.2/3.3/3.5) |
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
| Speicherwirkung +0,1…0,2 bar | Netzhebel nicht validiert; Struktur (2.3) | **Eher kleiner:** Maßgebend ist der Regelpunkt V06 im Süden. Eine Einspeisung im Osten wirkt dort mit +0,03 bar je 100 kg/s; 40 MW am Standort S ≙ ≈ 0,08 bar (0,04–0,11) KWK-Entlastung ≙ ≈ 1 Prozentpunkt Ausbaureserve. In der City +0,25 bar, maßgebend nur, solange die Mitte bindet. Bestätigung per Feldtest (3.3) oder validiertem Modell. Thermisch nur als n−1-Reserve: 30–60 MWh bei P90 | 2, 3, 5, 7 | V |
| Bestand kritisch, Defizit 15–19 bar·h | S-05, Auslegungsfall (2.1) | Bei Last 2025 **widerlegt** (Reserve ≈ 1,3 bar). Bei **Auslegungslast knapp ausreichend**: Anker 3,2–3,6 bar (West aus eigenen Kesseln), bei West-Bezug 3,9–4,5 bar. Süden bei P90 maßgebend; Prüfung gegen das Grenzband 4,0–5,7 bar und die Ost-Kopplung. Mit konsistentem Modell als erforderliche KWK-Δp P50/P90 bestätigen | 1, 2, 4 | A |
| Ausbau nur bis +5…10 % | S-05, S-02, Ausbauort | Anker bei Auslegungslast: +5…13 % bis 4,0 bar, +24…34 % bis 5,7 bar (West aus eigenen Kesseln). Die Größenordnung der Studie trifft den Fall „4,0 bar als Grenze“; die Herleitung ist falsch, und 4,0 bar ist nur ein Erfahrungswert. Exakt über die Aufnahmekapazität je Gebiet, mit Ost-Kopplung und Erzeugungsleistung | 2, 4, 6 | A |
| KWK-Limit ab +15 % | Limit = 2025-Beobachtung (2.2) | **Artefakt bestätigt** (KWK-Wärme P99 62 von 127 MW). Plangrenzen und Merit-Order; Ost-Erzeuger sind der eigentliche Engpass | 1, 4 | A |
| Druckanhebung ist der Haupthebel | per Konstruktion (2.2) | Die KWK-Δp wirkt mit 0,7–0,84 durch, ist aber über die Ost-Kopplung auf ≈ 3,6–4,3 bar begrenzt (MVA an der Pumpengrenze). Hebel ohne Investition: West bei Kälte aus eigenen Kesseln (≈ −0,7…0,9 bar erforderliche Δp), im heutigen Betrieb Ost-Vorlauf über der Heizkurve (≈ +0,8 bar wirksame Grenze). Kostenvergleich mit PS1/HW1-Nutzung, Booster und Rücklaufabsenkung | 1, 6 | A/V |
| Standort Innenstadt wirkt stärker | Lastverteilung nicht identifizierbar (3.4) | Verbundflüsse über den Tracer (3.5) bestimmen. Für den kritischen Süden sind lokale Einspeisung oder PS1 um ein Vielfaches wirksamer als der V22 | 2, 3, 5, 7 | V |
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
| Ostbereich auch mit konsistenter Struktur nicht validierbar | Aussagen räumlich begrenzen (Mitte/Süd/V22); Ost nur als Band; gezielte Messung an Arm. A1 und den Ost-Koppelstellen |
| Stundenwerte zu grob für Spitzen-Δp und Tracer (Laufzeiten 1–2 h) | Stunden-Min/Max (Stunden-Min/Max-Export), 15-min- oder Minutenwerte nutzen |
| Weitere Signalfehler wie beim GT-Signal | Duplikat- und Bilanzprüfung aller Signale als feste Prüfroutine in Phase 1 (Kopien, Hängewerte wie `pump_station_2_flow_return_to_center` = 1078, Einheitentest) |
| Kosten fehlen | technische Rangfolge mit Machbarkeit berichten; Kostenrangfolge als offener Punkt |
