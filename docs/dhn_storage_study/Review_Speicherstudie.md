# Fachliche Prüfung: Studie Großwärmespeicher Standort S (Netz DHN-A), Hydraulik und Druck

> **Anonymisierung:** Netz „DHN-A“. Verbraucher V01–V24; die Zuordnung zu den Klarnamen liegt nur lokal beim Auftraggeber. Erzeuger nach Typ:
> * KWK = Gas-KWK-Hauptanlage und Druckhalter
> * MVA = Abfallverbrennung
> * GT = Gasturbine
> * Bio-KWK = Biomasse-KWK
> * HW1/HW2 = Heizwerke; HW2 mit Wärmeübertrager zum Sekundärnetz West
> * PS1/PS2 = Pumpstationen
>
> Weitere Bezeichnungen: Speicherstandort **S = Verbraucher V22**; L1–L7 = Haupt- und Transportleitungen; N_… = Modellknoten; A1… = Armaturen; Plan A/B/C = Betreiberpläne (Erzeuger, Netz Mitte, Netz West). Datensatz und Spaltennamen: `data/dhn_a/README.md`.

Stand: 2026-10-01, Nachträge 2026-10-02 · Geprüfter Stand: Branch Studien-Branch, Commit `121196e` (Notebook Studien-Notebook, `docs/dhn_storage_study/Dokumentation_Skript_und_Annahmen.md`, `docs/dhn_storage_study/Datenanfrage_Betreiber.md`).

**Hinweis zur Weitergabe:** Der Bericht zitiert Kennzahlen aus der Studiendokumentation. Diese Kennzahlen sind dort als aus NDA-Daten abgeleitet gekennzeichnet. Vor einer externen Weitergabe deshalb freigeben lassen.

**Prüfumfang und Grenzen.** Die Messdaten (`data/dhn_a/`) liegen nicht im Repository. Das Notebook ist ohne Ausgaben eingecheckt. Ich konnte es daher **nicht ausführen**. Geprüft habe ich den Zelleninhalt aller 159 Zellen (Code, Gleichungen, Texte), das Annahmenregister und die Datenanfrage. Kernformeln und Annahmen habe ich unabhängig nachgerechnet (Abschnitt 5). Zahlenwerte aus Ergebnissen stammen aus der Studiendokumentation und sind als solche gekennzeichnet.

**Nachtrag (2026-10-01):** Nachträglich lagen die Messdaten 2025 (`measurements_2025_hourly.parquet`) und die Pläne Plan A, Plan B und Plan C vor. Damit habe ich die Befunde an Daten und Plänen geprüft (**Abschnitt 9**). Alle Hauptbefunde bestätigen sich. Hinzu kommen neue Befunde, u. a. ein **fehlerhaftes GT-Wärmesignal** und **gemessene Netzhebel**.

---

## 1. Gesamturteil

Die Studie ist methodisch sorgfältig aufgebaut und sehr transparent dokumentiert: Annahmenregister, Konfliktkatalog, getrennte Kalibrierung und Validierung, Tests, pandapipes-Kontrolle und Unsicherheitsanalyse sind vorhanden. Die **physikalischen Grundgleichungen sind korrekt umgesetzt**: Darcy–Weisbach in Druckhöhenform, Stoffwerte, Speicherbilanz und Gl. 15.1. Mehrere **qualitative Kernaussagen sind belastbar**:

* Ein direkt eingebundener Speicher kann ohne Pumpe nicht entladen.
* Die Speicherwirkung auf den Kunden-Differenzdruck ist klein.
* Laden zur Lastspitze ist schädlich.
* Der Standort ist für die Wirkung wichtiger als das Volumen.

**Nicht belastbar** sind dagegen die **quantitativen Aussagen zum heutigen Zustand und zum Ausbau**: „kritischer Bestand“, Δp-Defizit in bar·h, „Ausbau über +5…10 % nicht möglich“, „KWK-Limit ab +15 %“ und „Druckanhebung 0,5 bar nötig“. Sie werden im Wesentlichen von drei Annahmen erzeugt und nicht von der Netzphysik:

1. der ungünstigen Erzeugerdruckhaltung,
2. einem Auslegungsfall, der die Massenströme gegenüber dem gemessenen Tag sogar **senkt**,
3. Erzeugerlimits, die aus dem milden Jahr 2025 abgelesen statt aus den Plänen übernommen sind.

Hinzu kommt eine **strukturelle Schwäche der Druckrandbedingungen**: An KWK **und** MVA sind Vorlauf- und Rücklaufdruck fest vorgegeben, und es gibt keine Massenbilanz je Erzeuger. Zwei Ergebnisse sind sachlich zu korrigieren: der **Speicher-Auslegungsdruck (≈ 17 bar)** und die **Behältergeometrie**.

| Kernaussage der Studie | Urteil |
|---|---|
| Entladen nur mit Pumpe möglich (direkte Einbindung) | **korrekt** (Physik, Gl. 15.1) |
| Speicherwirkung klein (≈ +0,1…0,2 bar am kleinsten Kunden-Δp), Richtung positiv | **plausibel**, Richtung robust. Die Modellunsicherheit für Δp (RMSE 0,3–0,6 bar) ist aber größer als der Effekt |
| Laden zur Lastspitze verschlechtert die Lage | **korrekt/plausibel** |
| Standort Innenstadt wirkt stärker als V22 | **plausibel** (Netzhebel), hängt aber von der nicht identifizierbaren Lastverteilung ab (Befund 3.4) |
| Bestand ist kritisch, Δp-Defizit 15–19 bar·h | **nicht belastbar**: entsteht durch die Annahme S-05 (Befund 2.1) |
| Ausbau über +5…10 % nicht ohne Druckverletzung | **nicht belastbar** (S-05, S-02) |
| KWK-Erzeugerlimit ab +15 % überschritten | **Artefakt** (Limit = 2025-Beobachtung, Befund 2.2) |
| Druckanhebung ist der Haupthebel (≈ 0,5 bar heute) | Wirksamkeit im Modell **per Konstruktion** (+x bar an jedem Knoten); quantitativ **zirkulär** (0,5 bar < angesetzte Absenkung von 0,65 bar). Entscheidend ist die Machbarkeit; die im Plan vorhandene Grenze von 4,0 bar wurde nicht geprüft |
| Auslegungsdruck Speicher ≈ 17 bar Ü | **überschätzt** (Doppelzählung der Förderhöhe, Befund 2.4); „10 bar zu niedrig“ ist wahrscheinlich trotzdem richtig |
| Siedesicherheit bei 120 °C gegeben | **plausibel** |

---

## 2. Wesentliche Befunde (ändern Aussagen)

### 2.1 Das Bestandsdefizit ist ein Produkt der Annahme „ungünstige Erzeugerdrücke“ (S-05), nicht der Last

**Belege im Code:**

* `UNFAV = dict(vl=-0.4, rl=+0.25)` ist **hart codiert**. Die Begründung „≈ P5/P95 der Hochlaststunden“ wird im Notebook nirgends berechnet. Der Wert wird in allen Auslegungsszenarien gleichzeitig an **KWK und MVA**, an **Vorlauf und Rücklauf** und über **alle 24 h** angesetzt. Damit fehlen den Erzeugern 0,65 bar Differenzdruck.
* Relevant wäre die Verteilung der **Erzeuger-Druckdifferenz** (VL − RL), denn die Erzeuger regeln Δp. P5 des Vorlaufs und P95 des Rücklaufs fallen nicht gleichzeitig an; die Kombination ist ein konstruierter Extremfall.
* Zelle 108 (Gewichtungstest) rechnet ausdrücklich „am kritischen Bestandstag **ohne** ungünstige Erzeugerdrücke (**dort ist Stufe 1 nicht bindend**)“. Ohne S-05 hat der Bestand also **kein** Δp-Defizit.
* Die „erforderliche Druckanhebung heute“ liegt laut Dokumentation bei ≈ 0,5 bar und damit unter der angesetzten Absenkung von 0,65 bar. Das lässt sich streng begründen: Die Lasten sind im Modell feste Massenströme. Eine gleiche Verschiebung der Druckhöhe an beiden Druckrändern (KWK und MVA) verschiebt deshalb **alle** Knotendrücke des Teilnetzes um denselben Betrag, ohne die Flüsse zu ändern. Ohne S-05 steigt also jeder Kunden-Δp um genau 0,65 bar (bis auf Dichteeffekte). Weil 0,5 bar Anhebung das Defizit bereits beseitigen, hat **S1 ohne S-05 kein Δp-Defizit**. Die Maßnahme „Druckanhebung“ macht im Kern die Annahme rückgängig.
* Antwort 4 (Kap. 22) begründet „Ausbau über ca. +5…10 % nicht ohne Druckverletzungen“ mit der „Annahme: Erzeugerdrücke **wie 2025**“. Gerechnet wird aber mit den Drücken von 2025 **minus 0,65 bar Δp**. Der Text widerspricht dem Code.

**Verstärkt durch den Auslegungsfall (S-02/S-03):** `base_day_case(design=True)` behält die Wärmelast des Basistags bei (`heat_factor=1.0`) und hebt nur die Vorlauftemperatur auf 120 °C an. Damit **sinken** die Massenströme gegenüber dem gemessenen Tag um den Faktor f_m = (T_VL,beob − T_RL)/(120 − T_RL):

| T_VL,beob am Basistag | f_m (T_RL 50–60 °C) | Reibungsverluste |
|---|---|---|
| 105 °C | 0,75–0,79 | × 0,56–0,62 |
| 110 °C | 0,83–0,86 | × 0,69–0,73 |
| 113,7 °C (Heizkurve bei −3,7 °C) | 0,90–0,91 | × 0,80–0,83 |

Der „Auslegungsfall“ S1 ist hydraulisch also **milder** als der gemessene Basistag S0. Die Lastextrapolation aus Kap. 10.5.2 (`LAST_MODELL`, 216/269 MW) wird berechnet, aber **nirgends verwendet**. Eine Auslegungslast bei −14 °C, die über dem Basistag bei −3,7 °C liegt, fließt nicht ein. Last und Druckannahme wirken damit gegenläufig und undurchsichtig zusammen.

**Empfehlung:**
1. S1 **ohne** S-05 als Hauptfall ausweisen. S-05 nur als Sensitivität führen, abgeleitet aus Daten: P5 der Δp-Differenz der Erzeuger bei Hochlast, bezogen auf den Basistag.
2. Die Auslegungslast explizit über `heat_factor` setzen (z. B. P_Auslegung/P_Basistag aus `LAST_MODELL`) und f_m ausgeben.
3. Im Tornado (Kap. 21) den Faktor „S-05 an/aus“ ergänzen.
4. Antworten 3, 4 und 18 sowie die Management Summary umformulieren: „Defizit unter der Annahme dauerhaft um 0,65 bar reduzierter Erzeuger-Δp“.

### 2.2 Erzeugerlimits = beobachtetes Maximum 2025 statt Plankapazität (S-04/S-09)

`CAP = P99,9` der Flüsse von 2025. 2025 war mild (kältester Tagesmittelwert −7,3 °C), die Erzeuger wurden also nie an ihre Grenze gefahren. Das Notebook hat die **Plankapazitäten aus Plan A selbst transkribiert** (Kap. 9.1, Tabelle `erzeuger`), nutzt sie aber nicht:

* KWK: 127 MW / 2350 t/h bei AT −14 °C, 143 MW im Umlenkbetrieb
* MVA: 40 MW / 530 t/h; GT: 31 MW / 410 t/h; Bio-KWK: 13 MW / 190 t/h; HW1: 40 MW / 550 t/h

Die Aussagen „KWK-Limit ab +15 % Ausbau überschritten, ab +30 % ganztägig“ sowie Stufe 2 der Optimierung (`s^cap`) beruhen damit auf einem **Artefakt**. Datenanfrage A4 („Limit = 2025-Maximum“) fragt Werte ab, die in den Plänen bereits vorliegen.

Ebenso transkribiert und ungenutzt sind diese Planangaben:

* „**Max. Differenzdruck Austritt Werk KWK 4,0 bar**, Ost-Erzeuger 7,5 bar“
* die VL-Abschaltdrücke von MVA, GT und Bio-KWK (19,5/20,5/22 bar)

Damit lässt sich der **Spielraum der Druckanhebung** (Antworten 3, 18, 23) schon heute prüfen: die gemessene KWK-Δp bei Hochlast plus die erforderliche Anhebung, verglichen mit 4,0 bar. Die Studie behandelt diese Grenze stattdessen als vollständige Datenlücke (A1/A2).

Das ist entscheidend, weil die **Wirksamkeit** der Druckanhebung im Modell per Konstruktion feststeht: Aus demselben Grund wie in 2.1 erhöht „Erzeugerdruck +x bar“ den Kunden-Δp an **jedem** Knoten um genau x bar. Das entspricht einer Absenkung von Δp_min um x. Die Rangfolge „Druckanhebung schlägt jede bauliche Maßnahme“ (Antwort 23, Maßnahme M1) ist daher kein Rechenergebnis. Die eigentliche Frage ist allein die **Machbarkeit**: Pumpenreserve, die Δp-Grenze 4,0 bar am KWK, Abschaltdrücke und PN. Genau diese prüft die Studie nicht.

**Empfehlung:** Planwerte als Erzeugerlimits verwenden (2025-P99,9 höchstens als Sensitivität). Die Druckanhebung gegen 4,0 bar (KWK) und 7,5 bar (Ost) prüfen. Laut Plan A sind diese Δp-Werte Erfahrungswerte; sie gehören deshalb als untere Grenze eines Bands neben die Pumpengrenzen und Abschaltdrücke (`Datenanalyse_Auslegung.md`, Abschnitt 6).

### 2.3 Druckrandbedingungen: zwei Druckhalter, keine Massenbilanz je Erzeuger (M-06/M-07)

`solve_case` löst das Vorlauf- und das Rücklaufnetz **getrennt**, jeweils mit fest vorgegebener Druckhöhe an KWK **und** MVA. Daraus folgt:

* **Keine Massenbilanz je Erzeuger.** Die VL-Einspeisung von KWK bzw. MVA muss nicht gleich ihrer RL-Rücknahme sein. Geprüft wird nur die **Summe** im Vorlaufnetz (`inj_all = mv @ Ainc.T`, Test „Massenbilanz < 0,01 kg/s“). Die Kalibrierung vergleicht ebenfalls nur die VL-Einspeisung mit der Messung (`residuals`: `sim["inj_all"]`). Das Rücklaufnetz kann eine andere KWK/MVA-Aufteilung haben, ohne dass es auffällt.
* **Fester Rücklaufdruck an MVA = zweite Druckhaltung.** Im Verbund hält das KWK den Ruhedruck. Die Ost-Erzeuger regeln laut Plan A den **Differenzdruck** mit Rücklaufpumpen, ihr Rücklaufdruck stellt sich ein. Der kalibrierte RL-Offset an MVA von **+7,7 m (≈ 0,75 bar)** gegenüber −0,3 m im VL ist ein Fit-Parameter ohne physikalische Deutung und ein Hinweis auf diese Fehlmodellierung.
* **Die Einspeisung an den Druckrändern wird nicht auf ≥ 0 geprüft.** Bei Speicherbetrieb oder Ausbau kann ein Erzeuger rechnerisch zur Senke werden.
* **Symptome:** Drei von 13 freien Leitungsgruppen liegen an den Kalibriergrenzen (L3 = 5,0, L6 = L7 = 0,2). Die Ost-Auslastung liegt laut Dokumentation bei „> 2×“, die Innenstadt-Auslastung bei 0,17–0,18 (Befund 3.4). Der Ost-RMSE beträgt ≈ 0,8 bar.
* **Die pandapipes-Kontrolle (Kap. 20) übernimmt dieselben Randbedingungen** (Druckränder KWK/MVA, Einspeisungen aus dem Eigenmodell). Die Abweichung von 0,015 bar bestätigt daher die **Numerik**, nicht die **Modellannahmen**. Formulierungen wie „Modell ↔ pandapipes ≤ 0,015 bar“ in der Management Summary dürfen nicht als Modellvalidierung gelesen werden. *Nachtrag:* Die Gegenrechnung zum neuen Netzmodell rechnet pandapipes deshalb als geschlossenen Kreis: eine Druckhaltung, massenstromgeführte Erzeuger, Vor- und Rücklauf getrennt (`Netzmodell.md`, Abschnitt 4.7).

Für V22 ist das relevant: V22 liegt auf L5 zwischen KWK und den Ost-Erzeugern, also genau dort, wo sich die beiden Druckränder treffen.

**Empfehlung:**
1. Sofort-Check (Code in Abschnitt 6.1): Abweichung VL- gegen RL-Einspeisung je Erzeuger und minimale Einspeisung in allen Szenarien.
2. Mittelfristig konsistent formulieren: KWK als einziger Druckhalter im RL und Δp-geregelt im VL. MVA entweder als Massenstrom-Einspeiser (gemessen bzw. aus Q/ΔT abgeleitet) oder als Δp-geregelter Erzeuger mit **gleichem** Massenstrom in VL und RL (gekoppelter VL/RL-Löser).

### 2.4 Speicher-Auslegungsdruck ≈ 17 bar Ü ist überschätzt (Kap. 18.3, Antwort 13, G5)

`p_des_pump = 1,10·(p_VL,max am V22 + H_P,max)` addiert zwei Maxima, die physikalisch nicht zusammen auftreten:

* Liegt die Pumpe im kalten Strang (Rücklauf → Speicherfuß), ist der Druck am Speicher beim Entladen p_RL + H_P − h_L,RL ≈ **p_VL + h_L,VL**. Das liegt nur um die Strangverluste über dem Netz-Vorlaufdruck, nicht um die volle Förderhöhe.
* Beim Laden und im Stillstand liegt der Speicher zwischen p_RL und p_VL.
* Maßgeblich für die Auslegung ist der **Absperrdruck** der Pumpe über ihrem **Saugdruck**, also max_t(p_RL + H_0) mit H_0 ≈ 1,1–1,3·H_P, oder der Ansprechdruck des Sicherheitsventils.

Beispiel mit Werten in der Größenordnung der Studie (p_VL = 11, p_RL = 8,5 bar Ü, Strangverluste 1,15 bar):

* Notebook-Formel: **16,1 bar**
* physikalisch: ≈ 11,6 bar am Speicher, mit 10 % Reserve **≈ 12,7 bar**; mit Absperrreserve ≈ 13–14 bar

Die Aussage „Topologie-YAML 10 bar ist zu niedrig“ bleibt wahrscheinlich richtig (KWK-VL-Median 10,7 bar). „≈ 17 bar“ in der Datenanfrage A2 und in G5 ist zu korrigieren.

**Textfehler Antwort 15:** „… die Speicher-Auslegung von ≈ {p_des_pump} bar Ü [liegt] auch [unter PN16]“ ist unbedingt formuliert. Bei 17 bar ist der Satz falsch. Zelle 114 behandelt denselben Fall korrekt mit einer Bedingung.

### 2.5 Speichergeometrie und -konzept sind so nicht baubar (T-03/T-04)

* `h_tank_m = 20` mit dem Kommentar „H/D ≈ 1,7 → D ≈ 21 m“ ist falsch. Bei 5 000 m³ und H = 20 m ergibt sich **D = 17,8 m und H/D = 1,12**. Ein Zylinder mit D = 21 m und H = 20 m hätte 6 900 m³.
* Ein **einzelner Druckbehälter** mit D ≈ 18 m bei 10–17 bar braucht nach der Kesselformel (f ≈ 200 MPa, z = 0,85–1) eine Wandstärke von **≈ 55–100 mm**. Das ist für einen Großspeicher technisch und wirtschaftlich unrealistisch; zum Vergleich: D = 4 m bei 17 bar ≈ 22 mm.
* Realistische Konzepte sind mehrere schlanke Druckbehälter, eine **druckentkoppelte Einbindung** (Speicher auf niedrigem Druck, dann Pumpen für Laden **und** Entladen, Variante A entfällt) oder der Speicher als Teil der **Druckhaltung**.
* Bei direkter Einbindung muss der vollständig gefüllte Behälter dauernd an die Netzdruckhaltung angebunden sein oder eine eigene Druckhaltung (Gas- oder Dampfpolster) haben. Im abgesperrten Zustand führen Temperaturänderungen sonst zu großen Druckänderungen.
* Das Druckhaltekonzept bestimmt Auslegungsdruck, Anschlussverluste, Förderhöhen und die hydraulische Wirkung. Es sollte vor der Detailauslegung mit dem Auftraggeber geklärt werden (C2 der Datenanfrage).

---

## 3. Annahmen mit schwacher oder falscher Begründung

### 3.1 Kunden-Mindestdifferenzdruck 1,0 bar (S-06)
Die Begründung zitiert „Plan A Δp intern 0,8–1,3 bar“. Diese Spalte (`dp_intern_bar`, Tabelle `erzeuger`) beschreibt den **internen Druckverlust der Erzeugeranlagen** (KWK 1,1, MVA 0,8, GT 1,3 …) und ist **keine Kundenanforderung**. Für den Knoten HW2 (WÜ Westnetz), der zu den kritischen Knoten zählt, nennt der Plan selbst einen Differenzdruckbereich von **0,7…2,5 bar** am WÜ-Eintritt; das Kriterium 1,0 bar ist dort strenger als der Plan. Außerdem: 2025 lag P1 der Stationen bei ≈ 1,1–1,2 bar, ohne dass Störungen bekannt sind. Ein Grenzwert von 1,0 bar liegt damit sehr nahe am Normalbetrieb.
→ Den Wert aus den TAB der Betreiber übernehmen, für HW2 0,7 bar ansetzen und die Sensitivität 0,7–1,2 bar in der Ergebnisdarstellung zeigen, nicht nur im Tornado.

### 3.2 Durchflusseinheit m³/h (D-02)
Das Prüfverhältnis Q_gemessen/(V̇·960·4,2·ΔT) ≈ 1,04 **spricht eher für t/h**. Mit realen Stoffwerten (nachgerechnet) wäre zu erwarten:

* bei t/h: 1,040–1,042
* bei m³/h mit Zähler im Rücklauf: ≈ 1,025
* bei m³/h mit Zähler im Vorlauf: ≈ 0,99–1,00

Der Test trennt die Einheiten also nicht sicher. Das Notebook rechnet zudem **alle** Volumenströme mit ρ(T_VL) in Massenströme um, also mit der kleinstmöglichen Dichte (`rand_bed`). Die Massenströme sind daher systematisch um etwa 3–6 % zu klein, die Reibung um 6–12 %. Die k-Kalibrierung gleicht das zum Teil aus. Das Verhältnis Speicherstrom (aus MW berechnet) zu Netzflüssen bleibt aber verzerrt.
→ Einheit und Messort klären (E1). Dichte am Messort verwenden.

### 3.3 Validierung „V22 ±0,07 bar“ ist ein schwacher Beleg
V22 liegt hydraulisch nahe am Druckrand KWK (≈ 1,2 km), und seine Höhe wurde aus denselben Druckdaten abgeleitet. Ein kleiner Fehler im **Absolutdruck** ist dort fast zwangsläufig; Kap. 10.3 nennt für die Hydraulik KWK–V22 selbst nur R² = 0,13. Entscheidungsrelevant ist der **Differenzdruck**. Dessen RMSE liegt bei ≈ 0,3–0,6 bar (Mitte/Süd) und damit über der Speicherwirkung von 0,1–0,2 bar.
→ Die Aussage „V22, Innenstadt und Süd mit ±0,2–0,3 bar belastbar“ (Kap. 14.1) gilt für Absolutdrücke, nicht für Δp.

Außerdem: Die Δp-Bias-Korrektur (Kap. 16.2) verwendet Hochlaststunden des **ganzen** Jahres, also auch den Validierungszeitraum. Bias-korrigierte Δp-Werte sind damit nicht mehr unabhängig validiert.

### 3.4 Lastanteile der Sektionen (D-12)
Die kalibrierte Winter-Auslastung der Innenstadt (City, 150 MW Anschluss) von **0,17–0,18** ist im Wintermedian unplausibel niedrig. Die Ost-Sektionen liegen deutlich höher („> 2×“). Das ist vermutlich ein Ausgleichseffekt der Randbedingungen aus Befund 2.3: Die Ost-Wärme „verbleibt“ im Osten, weil der Transfer in die Stadt nicht abgebildet wird. Der **Standortvergleich N_City gegen V22** (Antwort 21, Empfehlung „Innenstadt statt V22“) hängt direkt an dieser Verteilung.
→ Plausible Auslastungsbänder (z. B. 0,3–0,7 im Wintermedian) als Grenzen oder Prior setzen und den Standortvergleich mit dieser Variante wiederholen.

### 3.5 Kalibrierung
* `objective` setzt nicht konvergierte Stunden auf Residuum 0 (`np.nan_to_num(..., nan=0.0)`). Der Optimierer kann damit Parameter „belohnen“, bei denen schwierige Stunden nicht konvergieren. → Anteil der nicht konvergierten Stunden ausgeben und bestrafen.
* Die RMS der normierten Residuen sinkt von 9,7 auf 2,7. Der Modellfehler ist damit fast dreimal so groß wie die angesetzte Messunsicherheit. Für Parameter an den Grenzen sind die Standardfehler aus (JᵀJ)⁻¹ nicht aussagekräftig.
* Die Markdown-Zelle in Kap. 13 sagt „Höhen bleiben auf den abgeleiteten Werten“. Der Code kalibriert aber 6 Höhen- bzw. Referenzoffsets (bis ±25 m).

### 3.6 Höhen aus Schwachlast (D-06)
„Schwachlast“ wird über `gas_CHP_flow_total_out` ausgewählt, also nur über die **positiven** SL-Flüsse. Im Sommer speist der Osten über L5/L1 in die KWK-Sammelschiene. Entlang L5/L1 (also an V22) kann deshalb Reibung im abgeleiteten „Höhen“-Offset stecken: bei ≈ 20 MW Ost-Einspeisung grob 0,2 bar/km. V22 hat keine eigene RL-Druckmessung, die VL/RL-Kontrolle greift dort also nicht.
→ Zusätzlich nach kleinem |L1|-Fluss filtern.

---

## 4. Bewertung des Annahmenregisters (Dokumentation, Abschnitt 6)

Legende: ✓ plausibel/korrekt · ⚠ prüfen/Begründung schwach · ✗ falsch begründet oder ergebnisbestimmend ohne Datenbasis

| ID | Urteil | Kommentar |
|---|---|---|
| D-01 Überdruck | ✓ | Das Median-Argument (8,5 gegen 8,4 bar Ruhedruck) trägt. Das „Planfenster 6,1–9,1 bar“ trennt dagegen nicht (absolut 7,5 bar Ü läge auch darin). „Faktor 1,013 bar“ muss „Offset“ heißen |
| D-02 m³/h | ⚠ | Test spricht eher für t/h; ρ(T_VL) für alle Messstellen (3.2) |
| D-03 Signalbedeutung | ✓ | Bilanzidentitäten überzeugend |
| D-04, D-05, D-07 | ✓ | |
| D-06 Höhen | ✓/⚠ | plausibel; V22 möglicherweise reibungsbeeinflusst (3.6) |
| D-08, D-09 Maßstab/Bildanalyse | ✓ | gut gemacht, gegen YAML-Länge geprüft (−7 %) |
| D-10 Schätzlängen | ⚠ | wird über k ausgeglichen |
| D-11 West entkoppelt | ✓ | |
| D-12 Lastanteile | ⚠ | Innenstadt 0,17 unplausibel (3.4) |
| D-13 Schaltzustände | ⚠ | beide Varianten gerechnet, gut |
| D-14 Pumpstationen | ✓ | |
| M-01–M-03 | ✓ | Rauheit 0,1 mm plausibel |
| M-04/M-05 k-Multiplikatoren | ⚠ | 3 Gruppen an Grenzen; Symptom von 2.3. „Ost-Kanten L3/L6/L7“: L3 ist die Stammleitung KWK → Mitte-L3 (Mitte) |
| M-06 Druckränder KWK+MVA | ✗ | zwei Druckhalter, keine Massenbilanz je Erzeuger (2.3) |
| M-07 MVA-Offsets −0,3/+7,7 m | ⚠ | 0,75 bar Fit ohne physikalische Deutung |
| M-08 σ_p, σ_V | ⚠ | RMS 2,7 ⇒ Modellfehler ≫ σ |
| M-09 Kal./Val.-Zeitraum | ✓ | Validierung ohne Februar-Spitze, wie dokumentiert |
| M-10 | ✓ | |
| M-11 Bias-Korrektur | ⚠ | nutzt Validierungszeitraum; Knoten ohne Messung = 0 |
| M-12 U' 0,3 W/(m K) | ⚠ | für ältere große Hauptleitungen eher niedrig (Verluste unterschätzt, wie dokumentiert) |
| S-01 Heizkurve | ✓ | Vorgabe, korrekt umgesetzt |
| S-02 Basistag als Auslegung | ✗ | Last nicht skaliert, `LAST_MODELL` ungenutzt, Massenströme sinken (2.1) |
| S-03 ṁ aus Q/(c_p ΔT) | ✓ | physikalisch korrekt, Wirkung siehe S-02 |
| S-04/S-09 Erzeugerlimits | ✗ | Planwerte vorhanden (2.2) |
| S-05 ungünstige Erzeugerdrücke | ✗ | hart codiert, nicht aus Daten, erzeugt das Bestandsdefizit (2.1) |
| S-06 Δp_min 1,0 bar | ⚠/✗ | falsche Planreferenz; HW2 laut Plan 0,7 bar (3.1) |
| S-07, S-08 | ✓ | |
| S-10 Auslastung 2,5 m/s; 750/500/300 t/h | ✓ | 1,5–1,8 m/s nachgerechnet |
| S-11 √-Näherung | ✓ | als Vergleichsgröße in Ordnung |
| S-12–S-15 | ✓ | transparent |
| T-01 Druckspeicher direkt | ✓ (Vorgabe) | Druckhaltekonzept fehlt (2.5) |
| T-02 V22-Knoten | ✓ | |
| T-03 5 000 m³ / 40 MW | ✓ | 40 MW ≙ 146 kg/s, v = 2,2 m/s in DN300 (nachgerechnet) |
| T-04 H = 20 m, Einzelbehälter | ✗ | D = 17,8 m (nicht 21 m); als Druckbehälter nicht realistisch (2.5) |
| T-05 DN300, 250 m, ζ = 12 | ✓ | Strangverlust 0,57 bar nachgerechnet |
| T-06–T-08 | ✓ | |
| T-09 56–58 MWh | ✓ | 56,4 MWh nachgerechnet |
| O-01, O-02, O-04 | ✓ | lexikographische Stufen korrekt implementiert |
| O-03 ein Tag, periodisch | ⚠ | mehrtägige Kälteperiode: nächtliches Nachladen ist dann nicht gesichert |
| U-01/U-02 | ✓/⚠ | S-05 wird nur ±0,3 bar um die Annahme variiert, nicht an/aus |

---

## 5. Unabhängig nachgerechnet (korrekt)

| Größe | Studie | Nachrechnung |
|---|---|---|
| Stoffwerte: Kell-Dichte, Vogel-Viskosität, p_sat (Wagner–Pruss), c_p-Tabelle | Tests in 12.1 | Koeffizienten und Referenzwerte geprüft ✓ (p_sat(120 °C) = 1,987 bar abs) |
| Rohrwiderstand ΔH = λL/(2gDρ²A²)·ṁ\|ṁ\|, Swamee–Jain | Kap. 11.3/12.2 | ✓ |
| Löser: Inzidenzvorzeichen, Pumpengewinn, mehrere Druckränder, Rücklauf mit −Einspeisung | `solve_network`, `solve_case` | ✓ (Numerik). Zur Modellannahme siehe 2.3 |
| Speicherenergie 5 000 m³ bei 10 K | 56–58 MWh | 56,4 MWh ✓ |
| Nutzbare Energie 120/55 °C, η_strat 0,85 | 5–8 h bei 40 MW | 312 MWh ≈ 7,8 h ✓ |
| 40 MW Entladung | ≈ 147 kg/s | 146 kg/s, v = 2,20 m/s, Re = 2,7·10⁶, λ = 0,0156 ✓ |
| Anschlussverlust je Strang (DN300, 250 m, ζ = 12) | – | 6,1 m ≙ 0,57 bar; beide Stränge 1,15 bar ✓ |
| Förderhöhe Entladen | 3–4,5 bar | Δp_S (2–3 bar) + 1,15 bar ✓ |
| Transportgrenzen 750/500/300 t/h | 1,5–1,8 m/s | 1,73/1,50/1,77 m/s ✓ |
| Heizkurve 110 − T_a, begrenzt 90…120 °C | Endpunkt-Tests | ✓ |
| Gl. 15.1/15.2 (Entladen nur mit Pumpe, Laden über Netz-Δp) | Kap. 15 | ✓ |
| Optimierung (SLP + MILP, nichtlineare Nachrechnung) | Kap. 17 | Struktur korrekt ✓ |

Hinweis: DN wird durchgehend als Innendurchmesser verwendet. Für Stahlrohre gilt z. B. DN400 → d_i ≈ 394 mm (Δp +8 %) und DN300 → d_i ≈ 313 mm. Die k-Kalibrierung gleicht das aus; für den Speicheranschluss ist die Rechnung leicht konservativ.

---

## 6. Empfohlene Prüfschritte (Code zum Einfügen ins Notebook)

### 6.1 Massenbilanz je Erzeuger und Vorzeichen der Druckrand-Einspeisung (nach Kap. 17.2)
```python
for sid, v in RUN.items():
    r = v["res"]; inj_v = r["inj_all"]; inj_r = -(r["mr"] @ Ainc.T)      # RL: Rücknahme je Knoten
    for nd in ("KWK", "MVA"):
        i = nidx[nd]; d = inj_v[:, i] - inj_r[:, i]
        print(f"{sid:6s} {nd}: max|VL−RL| = {np.abs(d).max():6.1f} kg/s ({100*np.abs(d).max()/max(np.abs(inj_v[:, i]).max(), 1):4.1f} %), min VL-Einspeisung = {inj_v[:, i].min():6.1f} kg/s")
```
Bei Abweichungen über wenige Prozent oder negativen Einspeisungen ist die Formulierung nach 2.3 umzustellen.

### 6.2 Wirkung von S-05 und des Auslegungsfalls (nach Kap. 16.3)
```python
print("Massenstromfaktor f_m im Auslegungsfall:", base_day_case(design=True).f_mass.describe().round(3).to_dict())
for lab, kw in (("S0 gemessen", dict(design=False)), ("S1 ohne S-05", dict(design=True, unfav=False)), ("S1 mit S-05", dict(design=True))):
    k = evaluate("x", base_day_case(**kw))["kpi"]
    print(f"{lab:14s} Δp_min {k['Δp_Kunde,min [bar]']:.2f} bar | Defizit {k['Δp-Defizit [bar·h]']:.1f} bar·h | KWK max {k['KWK-Durchfluss,max [m³/h]']:.0f} m³/h")
# S-05 aus Daten: Δp der Erzeuger bei Hochlast relativ zum Basistag
hq = BC.index[BC.valid & (BC.R >= BC.R[BC.valid].quantile(0.9))]; bd = BC.loc[BC.index.date == BASE_DAY.date()]
for nd in ("kwk", "mva"):
    dp = (BC[f"pVL_{nd}"] - BC[f"pRL_{nd}"])[hq]; dp0 = (bd[f"pVL_{nd}"] - bd[f"pRL_{nd}"]).mean()
    print(f"{nd.upper()}: Δp Basistag {dp0:.2f} bar, P5 Hochlast {dp.quantile(.05):.2f} bar → Abschlag {dp.quantile(.05)-dp0:+.2f} bar (Studie: −0,65 bar)")
```

### 6.3 Erzeugerlimits und Spielraum der Druckanhebung aus Plan A
```python
CAP_PLAN = {"KWK": 2350/3.6, "MVA": 530/3.6, "GT": 410/3.6, "Bio-KWK": 190/3.6, "HW1": 550/3.6}   # t/h → kg/s, AT −14 °C (Plan A)
print({k: (round(CAP[k]), round(v)) for k, v in CAP_PLAN.items()}, "(2025-P99,9 gegen Plan, kg/s)")
dpH = (m.gas_CHP_p_supply - m.gas_CHP_p_return)[hq]
print(f"KWK-Δp bei Hochlast: P50 {dpH.median():.2f}, P95 {dpH.quantile(.95):.2f}, max {dpH.max():.2f} bar → Reserve bis 4,0 bar (Plan A): {4.0 - dpH.quantile(.95):.2f} bar")
```

### 6.4 Speicher-Auslegungsdruck korrekt ableiten (ersetzt `p_des_pump` in Kap. 18.3)
```python
iM = nidx["V22"]; p_side = []
for v in RUN.values():
    if v.get("plan") is None: continue
    hp = v["h"].Hp_bar.values; dis = v["m"] > 0
    p_side.append(np.where(dis, v["pr"][:, iM] + 1.2*hp, v["pv"][:, iM]))   # Entladen: Saugdruck + Absperrhöhe (≈1,2·H_P); sonst Netz-VL
p_des_korr = 1.10*np.concatenate(p_side).max()
print(f"Auslegungsdruck Speicherseite (Pumpe im kalten Strang, Absperrreserve 20 %, +10 %): {p_des_korr:.1f} bar Ü (bisher {p_des_pump:.1f})")
```
Danach Antwort 15 an die Bedingung `p_des < 16` knüpfen (wie in Zelle 114).

### 6.5 Kalibrierung: Nichtkonvergenz bestrafen
In `objective` statt `nan_to_num(..., nan=0)` die nicht konvergierten Stunden mit einem festen Strafwert belegen (z. B. 5σ je Residuum) und ihren Anteil ausgeben. Fehlende Messwerte bleiben weiterhin 0.

---

## 7. Kleinere Fehler und Inkonsistenzen

* Kap. 10.5.8: „Spitzenlast Februar 2025 ≈ 183 MW Tagesmittel“; Kap. 16.1 und Dokumentation: 14.02.2025 ≈ 215 MW. Zahlen vereinheitlichen und die Bezugsgröße nennen (Verbund mit oder ohne West bzw. HW2-Kessel).
* Rechenzeit im Notebook-Kopf 15–20 min, in der Dokumentation 45–60 min.
* Kap. 11.4 (η 0,6–0,8) und 11.6 (Δp_min 0,3–1,5 bar) nennen Sensitivitätsbereiche, die in Kap. 21 nicht gerechnet werden (dort 0,8–1,2 bar, η nicht variiert).
* Monte-Carlo (Kap. 21) verwirft fehlgeschlagene Läufe stillschweigend (`except Exception: pass`). Anzahl ausgeben.
* `with_theta` ist zweimal definiert. Toter Code: erste `Re`-Zeile in `edge_resistance`, `EDGE_CAP … if False else …`, `ax.add_patch(...) if False else None`.
* `pa` in Kap. 10.7 stammt aus Modell v0.1 (V22 mit 32 MW Anschluss im Ost-Anteil `s13`), obwohl V22 separat gemessen wird.

---

## 8. Priorisierte Empfehlung

1. **Sofort (ohne Betreiberdaten):** Checks 6.1–6.3 laufen lassen. S1 ohne S-05 als Hauptfall zeigen, Auslegungslast explizit skalieren, Erzeugerlimits und Δp-Grenze 4,0 bar aus Plan A einsetzen. Auslegungsdruck nach 6.4 korrigieren, Textfehler Antwort 15 beheben.
2. **Modell:** Druckrandbedingung umstellen (KWK als einziger Druckhalter, MVA mit gekoppeltem VL/RL-Massenstrom). Lastanteile auf plausible Auslastungen begrenzen und danach Kalibrierung, Standortvergleich und Maßnahmenrangfolge wiederholen.
3. **Konzept:** Behältergeometrie und Druckhaltekonzept des Speichers mit dem Auftraggeber klären (direkt mit Netzdruck, mehrere Behälter oder druckentkoppelt), bevor Pumpe und Anschluss ausgelegt werden.
4. **Kommunikation:** In Management Summary und Antworten zwischen „physikalisch belastbar“ (Pumpe nötig, kleine Wirkung, Laden zur Spitze schädlich) und „annahmegetrieben“ (Bestandsdefizit, Ausbaugrenze, KWK-Limit, 17 bar) unterscheiden.

---

## 9. Nachtrag: Prüfung mit Messdaten 2025 und Plänen

**Datenbasis:**
* `measurements_2025_hourly.parquet`: 8 759 Stunden × 169 Signale, 2025
* Plan A „Erzeugerausspeisungen und -umwälzungen bei Ausfall der größten Erzeugungsleistung“ (Stand 14.06.2023)
* Plan B Netz Mitte (Stand 28.10.2022)
* Plan C Netz West (Stand 25.03.2022)

**Nicht vorhanden:** Außentemperatur (15-min-Importdaten), Signalindex, Lastgänge 2020–2022 und Stunden-Min/Max. Die Auswertungen kommen deshalb ohne Außentemperatur aus. „Hochlast“ ist hier wie in der Studie das obere 10-%-Quantil der Erzeugung (n = 771 h). Die Auswerteskripte sind wegen NDA nicht versioniert; unten stehen nur aggregierte Kennzahlen.

### 9.1 Prüfung der Review-Befunde

| Befund | Prüfung | Ergebnis |
|---|---|---|
| **2.1 S-05** (−0,4/+0,25 bar) | Erzeugerdrücke in den Hochlaststunden relativ zum Basistag | KWK: P5 der Δp nur **−0,18 bar** unter dem Basistag; MVA: **−0,33 bar**. Die Studie setzt −0,65 bar an. VL ≤ P5 **und** RL ≥ P95 traten in **0 %** der Hochlaststunden gleichzeitig auf. **Bestätigt:** S-05 ist 2- bis 3,5-mal zu groß und als Kombination nie beobachtet |
| **2.1 Auslegungsfall** | KWK-Temperaturen am 14.02.2025 | T_VL 111,4 °C, T_RL 58,7 °C ⇒ f_m = 0,86, Reibungsverluste × 0,74 gegenüber dem gemessenen Tag. **Bestätigt** |
| **2.1 Basistag „≈ 215 MW“** | Erzeugung nach der Definition der Studie (KWK netto + MVA + Bio-KWK + „GT“ + HW1 + HW2-Kessel), Tagesmittel | 14.02.2025 ≈ **169 MW**. Die höchsten Tage sind der 17.–19.02.2025 mit ≈ 181–183 MW; das entspricht den 183 MW aus Kap. 10.5.8. **215 MW sind nicht reproduzierbar**, und der 14.02. ist auch unter den vollständig gemessenen Tagen nicht der höchste |
| **2.2 Erzeugergrenzen** | Plan A gelesen, mit Daten 2025 verglichen | Details unter der Tabelle. **Bestätigt**, und präzisiert: Bei Ausbau ist nicht das KWK knapp, sondern die **Ost-Erzeugung und die Ost-Förderhöhe** |
| **2.3 Druckhaltung** | Plan A, Plan B | Plan A: KWK „Ruhedruckanbindung auf P-Saugseite“, MVA „Ruhedruck (**Notbetrieb**)“, GT und HW1 „Ruhedruck (**Inselbetrieb**)“. Plan B: „Die RL-Absperrarmatur muss (zur Sicherstellung der Druckhaltung) offen bleiben.“ **Bestätigt:** Im Verbund ist das KWK der einzige Druckhalter; ein fester RL-Druck an MVA widerspricht dem Plan |
| **3.1 Δp_min 1,0 bar** | Kunden-Δp 2025; Plan A-Kopfzeilen | **V06** (Süd) liegt in 106 h unter 1,0 bar (21 h davon in Hochlast), **HW2-Prim** in 276 h unter 1,0 bar und in 50 h unter 0,8 bar. Das ist Normalbetrieb ohne bekannte Störung. „Δp intern“ steht in Plan A im Kopf **jeder Erzeugeranlage**; für die HW2-WÜ nennt der Plan 0,7–2,5 bar am Eintritt. **Bestätigt** |
| **3.2 Durchflusseinheit** | Q gegen ṁ·Δh mit Stoffwerten | Kundenstationen (V07, V22, V14, V05, V15, HW2-Prim): **t/h passt auf 0,1–0,3 %**, m³/h mit ρ(T_VL) liegt 4–5 % daneben. KWK-Stammleitungen: t/h passt am besten (0,98). Bio-KWK: m³/h im Vorlauf. Laut Plan B wird der SL-Durchfluss **im Rücklauf** gemessen. **Bestätigt:** Die Studie unterschätzt die Massenströme um ≈ 4–5 % |
| **3.4 Lastverteilung** | Energiebilanz im Winter und Temperatur-Tracer | Details unter der Tabelle. **Bestätigt:** Die niedrige City-Auslastung der Studie spiegelt fehlende Verbundflüsse wider, keine geringe Last |

**Details zu 2.2 (Erzeugergrenzen):**
* **KWK:** Max. Δp am Werksaustritt 4,0 bar, Pumpen 2×1000 + 2×900 t/h bei 73,5 m, 127 MW (143 MW im Umlenkbetrieb), 2350 t/h.
  * 2025 lag die KWK-Δp in Hochlast bei P95 3,21 bar (max. 4,16). Die **Reserve bis 4,0 bar beträgt ≈ 0,8 bar**.
  * KWK-Wärme: P99 62 MW (max. 91) von 127 MW, also **große Reserve**.
* **Ost und HW1:**
  * MVA: max. 46 MW (Plan 40/45); Bio-KWK: 15,4 MW (Plan 13/14,5); HW1: 569 t/h (Plan 550). Diese Erzeuger lagen **2025 an ihrer Grenze**.
  * MVA-Δp lag in 390–550 h über 7,5 bar. Laut Fußnote des Plans ist der Wert ein Erfahrungswert, keine harte Grenze.
* „KWK-Limit ab +15 %“ ist damit ein Artefakt. Zusatzlast muss vom KWK kommen.

**Details zu 3.4 (Lastverteilung):**
* Winter-Median: Die Ost-Erzeugung liegt bei ≈ 89 MW (GT gemessen). Nur ≈ 4 MW fließen davon über L1/L3 ins KWK.
* L2 liefert 25 MW für 151 MW Anschluss; das ergibt eine Auslastung von 0,16.
* Ost-Wasseranteil aus dem Temperatur-Tracer (Mischungsregression bei T_Ost ≠ T_KWK, Winter, n = 287 h):

| Station | Ost-Wasseranteil | R² |
|---|---|---|
| V22 | ≈ 75 % | 0,63 |
| V11 | ≈ 85 % | |
| V15 | ≈ 64 % | |
| V23 | ≈ 49 % | |
| V17 (City) | ≈ 28 % | 0,28 |

* Ost-Wasser erreicht also die City. Die Verbundkanten tragen deshalb wahrscheinlich **erheblich** (Größenordnung 30–45 MW bei gleicher Auslastung aller Gebiete), nicht null.

### 9.2 Neue Befunde

**N1 – Das GT-Wärmesignal ist eine Kopie der Westnetz-Wärme.**
* `gas_turbine_heat` ist in allen 8 757 Stunden identisch mit `boiler_plant_2_secondary_heat`. Das HW2-Signal ist echt: Es passt zu den Sek-Durchflüssen (Verhältnis 0,996).
* Wenn die GT steht (27 % der Stunden mit T_VL < 60 °C), „liefert“ das Signal im Median 5,7 MW.
* Aus V̇·Δh, wo der GT-Durchfluss gemessen ist (35 % der Stunden), ergeben sich im Median 23 MW gegenüber 17 MW im Signal; die Korrelation beträgt nur 0,7.
* Folgen für die Studie:
  * GT-Einspeisung (`m_gt = Q/ΔT`) und Ost-Erzeugung,
  * Gesamterzeugung, Basistag und Lastregression,
  * die Aussage „Ost speist 60 %“,
  * die Ost-Kalibrierung. Das ist eine wahrscheinliche Mitursache der Parameter an den Grenzen.

→ Dem Betreiber melden und das richtige GT-Signal anfordern. Bis dahin GT nur aus V̇·Δh verwenden.

**N2 – Die kritischste Δp-Messung wird nicht genutzt.**
* V06 (Süd, P1 0,9 bar), V03 und V10 (City), V07 und V19 haben nur ein `DiffDruck`-Signal. Der Code der Studie verlangt für die Δp-Validierung und die Bias-Korrektur `Druck_VL` **und** `Druck_RL` und lässt diese Stationen daher aus.
* Wo beides vorhanden ist, stimmt `DiffDruck` auf ±0,1 bar mit VL − RL überein (r = 0,99).

**N3 – Der Betrieb hält den Kunden-Δp; die Erzeugerdrücke sind nicht fest.**

| Lastdezil (Erzeugung) | KWK-Δp | min. Δp Mitte-Stationen (P50 / P10) | V06 (P50 / P10) |
|---|---|---|---|
| unterstes (≈ 27 MW) | 1,77 bar | 1,6 / 1,3 | 1,5 / 1,2 |
| mittleres (≈ 87 MW) | 2,58 bar | 1,8 / 1,3 | 1,2 / 1,2 |
| 8. (≈ 123 MW) | 2,93 bar | 1,8 / 1,5 | 1,2 / 1,1 |
| oberstes (≈ 161 MW) | 2,53 bar | 1,6 / 1,3 | 1,2 / 1,1 |

* Die KWK-Δp wird lastabhängig nachgeführt (r = 0,66), die Kunden-Δp bleiben nahezu konstant. Das entspricht einer Schlechtpunkt- oder Kennlinienregelung.
* Szenarien mit festgehaltenen Erzeugerdrücken bilden den Betrieb nicht ab. Das stützt die Umstellung auf „erforderliche Förderhöhe“ im Plan.

**N4 – Netzhebel gemessen** (Regression auf stündliche Differenzen, n ≈ 4 900 h, 660 Stunden mit HW1-Sprung > 72 t/h; kontrolliert für KWK-Δp, MVA-Δp, Last und PS1-Gewinn)

| Station | je 100 kg/s Einspeisung HW1 (Süd) | je bar KWK-Δp | je bar MVA-Δp | je bar PS1-Gewinn | je 10 MW Last |
|---|---|---|---|---|---|
| V06 (Süd) | **+1,01** ± 0,02 bar | 0,69 | −0,05 | +0,30 | −0,14 |
| V12 (L4) | +0,06 | 0,84 | 0,03 | −0,13 | −0,07 |
| V03 (City) | +0,10 | 0,84 | 0,05 | −0,11 | −0,07 |
| V10 (City) | +0,12 | 0,84 | 0,04 | −0,12 | −0,08 |
| V24 (City) | +0,07 | 0,84 | 0,03 | −0,12 | −0,07 |
| V23 (L1) | +0,02 | 0,84 | 0,02 | −0,12 | −0,06 |
| V22 | +0,04 | 0,74 | **0,19** | −0,07 | −0,05 |
| V15 (Mitte-L3) | +0,11 | 0,75 | **0,19** | −0,06 | −0,08 |
| HW2-Prim | +0,05 | 0,71 | −0,04 | −0,11 | −0,03 |

Folgerungen:
* Lokale Einspeisung wirkt **stark lokal** (V06 +1 bar je 100 kg/s) und **schwach entfernt** (City +0,07…0,12 bar; mit korrigierter Last +0,17…0,20 bar, siehe `Datenanalyse_Auslegung.md`, Abschnitt 7). Das stützt die qualitative Aussage der Studie, dass die Speicherwirkung lokal ist. *Nachtrag:* Die massenstromkonsistente Auswertung und das Netzmodell zeigen, dass ein Ersatz von KWK-Wasser alle Stationen spürbar anhebt; „klein“ gilt nur für den Engpass im Süden (`Netzmodell.md`, Abschnitt 5.1).
* Der kritischste Knoten (V06/Süd) profitiert vor allem von **Einspeisung im Süden oder von PS1**, nicht von einem Speicher am V22.
* Die KWK-Δp wirkt mit 0,7–0,84 statt 1,0 auf die Kunden durch, weil die Ost-Erzeuger mitregeln. Die 1:1-Verschiebung des Studienmodells überschätzt die Druckanhebung etwas. *Nachtrag (Netzmodell):* Mit einer Druckhaltung und massenstromgeführten Ost-Erzeugern ist der Durchgriff strukturell 1. Die gleiche Regression auf Modellwerten ergibt an Mitte und City 0,97–1,03, gemessen 0,83–0,96; an V06 senkt die Regelung den Wert stark. Ein Durchgriff unter 1 ist deshalb zum Teil ein Effekt der Regression (`Netzmodell.md`, Abschnitt 4.2).
* **Diese Hebel sind die Validierungsziele** für jedes Netzmodell (Plan, Phase 3).

**N5 – Auslegungsfall in Plan A.** Das Blatt gilt „bei Ausfall der größten Erzeugungsleistung“ (n−1). Das KWK ist dort mit „2350 t/h (= 127 MW bei 107 °C − 60 °C)“ angegeben, die Ost-Erzeuger mit 125/60 °C. *Geklärt mit DWD-Temperaturen* (`Datenanalyse_Auslegung.md`, Abschnitt 3): Der Betrieb folgt der Vorgabe-Heizkurve und erreicht ≈ 120 °C ab −10 °C. Die 107 °C beschreiben den Arbeitspunkt der Mengenangabe, nicht die Fahrweise. Die Auslegungsspreizung beträgt ≈ 61 K (120/59 °C).

**N6 – Mindest-Ruhedruck je Netzbereich (Plan B).** Am Ruhedruckbalken des KWK gelten bei 130/120/110/100 °C:

| Netzbereich | 130 °C | 120 °C | 110 °C | 100 °C |
|---|---|---|---|---|
| MITTE-City | 7,2 | 6,5 | 6,0 | 5,6 bar |
| Mitte-City/Mitte-L4/Mitte-L3/L1/L4 | 4,0 | 3,2 | 2,6 | 2,5 bar |
| SÜD | 4,0 | 3,2 | 2,6 | 2,5 bar |
| OST | 2,5 | 2,5 | 2,5 | 2,5 bar |

Das ist die direkte Prüfgröße für die Siedesicherheit und begrenzt die Alternative „Rücklaufdruck absenken“ (2025: KWK-RL min. 6,96 bar).

**N7 – Datenbasierter Plausibilitätsanker** (indikativ)

Der Druckverlust vom KWK zur ungünstigsten Mitte-Station folgt ≈ 0,28 + 4,1·10⁻⁵·P² bar (P = Verbundeinspeisung in MW, R² = 0,75). Daraus ergibt sich die erforderliche KWK-Δp für 1,0 bar in der City:

| Last | erforderliche KWK-Δp |
|---|---|
| Höchstlast 2025 (P = 187 MW, stündlich) | ≈ 2,7 bar |
| +20 % | ≈ 3,3 bar |
| +40 % | ≈ 4,1 bar |

Mit dem Fluss L2 + L4 als Lastgröße liegt +20 % bei ≈ 3,9 bar. Einschränkungen: quadratische Extrapolation, Erzeugeraufteilung wie 2025, Süd/V06 hängt zusätzlich an PS1 und HW1.

**Korrektur (nach Auswertung von Wetterdaten, Lastgängen und Rücklaufmessung):** Die Werte oben beziehen sich auf die **Last 2025**, ein mildes Jahr mit einem kältesten Tag von −5,6 °C.

Bei **Auslegungslast** gilt:
* Annahmen: −14 °C, n−1 nach Plan A, unbegrenzter Bedarf aus den Lastgängen 2020–2022 und 2025, gemessener Rücklauf 59 °C, Westnetz aus eigenen Kesseln (Plan A).
* Das KWK braucht **≈ 3,2–3,6 bar**. Bei P90 ist der **Süden** maßgebend, nicht die City.
* Ausbaureserve bis 4,0 bar (Erfahrungswert laut Plan A): **+5…13 %**; bis zur Pumpengrenze ≈ 5,7 bar: +24…34 %.
* Bezieht das Westnetz wie 2025 Wärme aus dem Verbund, sind es 3,9–4,5 bar.
* Die KWK-Δp ist über die Kopplung an die Ost-Erzeuger (MVA an ihrem Δp-Erfahrungswert) heute nur bis ≈ 3,6–4,3 bar nutzbar.

Der Bestand ist bei Last 2025 nicht kritisch, bei Auslegungslast **knapp ausreichend**. Siehe `Datenanalyse_Auslegung.md`, Abschnitte 1, 5 und 6.

**N8 – PS1 ist aktiv, nicht nur Bypass.** Die PS1 läuft in 82 % der Hochlaststunden mit ≈ 0,6 bar Gewinn (P95 1,3 bar). Installiert sind 2×429 m³/h bei 40 m (≈ 3,7 bar). Das ist eine vorhandene Reserve für den Süden; je bar PS1-Gewinn steigt der Δp an V06 um +0,3 bar.

**N9 – Datenqualität:**
* `pump_station_2_flow_return_to_center` hängt in 2,5 % der Stunden bei 1078.
* `pump_station_2_flow_return_to_west` hat 1 % Abdeckung, `pump_station_1_flow_return_to_south` 7 %.
* `boiler_plant_2_hx_heat` zeigt 2 Spitzen über 40 MW.

### 9.3 Konsequenzen für die Kernaussagen

| Aussage der Studie | Stand nach Datenprüfung |
|---|---|
| „Bestand kritisch“ | **Bei Last 2025 widerlegt**: alle Mitte-Stationen ≥ 1,1 bar (P1), ≈ 1,3 bar Reserve am KWK. **Bei Auslegungslast knapp ausreichend**: erforderliche KWK-Δp ≈ 3,2–3,6 bar mit Westnetz aus eigenen Kesseln (3,9–4,5 bar bei West-Bezug), gegen 4,0 bar Erfahrungswert bzw. ≈ 5,7 bar Pumpe. Die Begründung der Studie (S-05) ist trotzdem falsch. Die KWK regelt auf den Süd-Schlechtpunkt V06 (≈ 1,2 bar), gehalten über PS1 und HW1. Das kalibrierte Netzmodell bestätigt den Befund: 3,0–3,4 bar (P50) bzw. 3,55–4,03 bar (P90) über drei gleich gute Kalibrierungen (`Netzmodell.md`) |
| „Ausbau nur +5…10 %“ | **Größenordnung plausibel, Begründung falsch**: Bei Auslegungslast reicht die Reserve bis 4,0 bar am KWK für +5…13 %, bis ≈ 5,7 bar für +24…34 % (Westnetz aus eigenen Kesseln). Begrenzend sind die KWK-Δp, die Kopplung an die ausgelasteten Ost-Erzeuger und die Erzeugungsleistung, nicht S-05. Das Netzmodell ergibt −0,3…+10 % bis 4,0 bar und +11…21 % bis zur Pumpengrenze. 4,0/7,5 bar sind laut Plan A Erfahrungswerte |
| „Speicherwirkung klein und lokal“ | **Teilweise gestützt.** Am Regelpunkt V06 wirkt Ost- statt KWK-Wasser mit +0,15 bar je 100 kg/s, Süd-Einspeisung mit +1,02 bar. 40 MW am Standort S senken die erforderliche KWK-Δp bei Auslegung um 0,16–0,34 bar (gemessene Hebel) bis 0,6–1,1 bar (Netzmodell); das ist mehr als die „+0,1…0,2 bar“ der Studie. Die Ausbaureserve steigt aber nur um 1–8 Prozentpunkte, weil danach der Süden bindet (`Netzmodell.md`, Abschnitt 5.1). Die frühere Angabe von 0,08 bar beruhte auf einer verzerrten Regression (`Datenanalyse_Auslegung.md`, Abschnitt 7) |
| „Standort entscheidend“ | **gestützt**: Für den kritischen Süden wirken lokale Einspeisung oder PS1 um ein Vielfaches stärker als der V22 |
| „Druckanhebung ist der Haupthebel“ | qualitativ ja (KWK-Reserve ≈ 0,8 bar bis 4,0 bar). Sie wirkt aber nur zu 0,7–0,84 durch. *Nachtrag:* Strukturell ist der Durchgriff im Netzmodell 1. Die massenstromkonsistente Regression ergibt an den Mitte- und Ost-Stationen gemessen 0,83–0,96 (Modell 0,97–1,03), an V06 wegen der Regelung nur 0,35. Jede bar KWK-Δp hebt die MVA-Δp um 0,8–1,0 bar, und die MVA liegt bei Kälte an ihrer Pumpengrenze. Nutzbar sind deshalb heute nur ≈ 3,6–4,3 bar; mit 120 °C Ost-Vorlauf ≈ 0,8 bar mehr |
