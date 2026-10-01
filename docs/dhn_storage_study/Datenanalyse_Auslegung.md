# Datenanalyse DHN-A: Wetter, Auslegungslast, hydraulische Begrenzung und erforderliche KWK-Druckdifferenz

> **Anonymisierung:** Netz „DHN-A“. Verbraucher V01–V24; die Zuordnung zu den Klarnamen liegt nur lokal beim Auftraggeber. Erzeuger nach Typ:
> * KWK = Gas-KWK-Hauptanlage und Druckhalter
> * MVA = Abfallverbrennung
> * GT = Gasturbine
> * Bio-KWK = Biomasse-KWK
> * HW1/HW2 = Heizwerke; HW2 mit Wärmeübertrager zum Sekundärnetz West
> * PS1/PS2 = Pumpstationen
>
> Weitere Bezeichnungen: Speicherstandort **S = Verbraucher V22**; L1–L7 = Haupt- und Transportleitungen; N_… = Modellknoten; A1… = Armaturen; Plan A/B/C = Betreiberpläne (Erzeuger, Netz Mitte, Netz West). Datensatz und Spaltennamen: `data/dhn_a/README.md`.

Stand: 2026-10-01 · Bezug: `Plan_belastbare_Aussagen.md` (Arbeitspakete 1.4, 1.8–1.11, 3.2, 3.4–3.6, 4.1) und `Review_Speicherstudie.md` (Abschnitt 9).

**Hinweis zur Weitergabe:** Der Bericht beruht auf anonymisierten Betreiberdaten (Freigabe für dieses Repository liegt vor). Vor externer Weitergabe gesondert freigeben lassen.

## Datenbasis

| Quelle | Inhalt |
|---|---|
| Leitsystem 2025 | `measurements_2025_hourly.parquet`, 8 759 h × 169 Signale |
| Lastgänge | `generation_profiles_2020_2022_hourly.csv`, stündliche Fernwärmeerzeugung 2020–2022 |
| Wetter | DWD Climate Data Center, Referenzstation, Lufttemperatur stündlich 1955 – 09/2026 |
| Pläne | Plan A, Plan B, Plan C |

Die DWD-Zeitstempel werden in Ortszeit umgerechnet: bis 30.11.1996 MEZ, danach UTC.

**Reproduktion:** Der anonymisierte Datensatz liegt im Repository unter `data/dhn_a/`, einschließlich der Außentemperatur; siehe `data/dhn_a/README.md`. Dann:
```
python -m scripts.dhn_study.run_analyse
python -m pytest -o addopts="" tests/test_dhn_study.py
```
Laufzeit ≈ 3 s. Die Ergebnisse stehen unter `results/dhn_study/datenanalyse/` (CSV und `zusammenfassung.md`). Der Code liegt in `scripts/dhn_study/` (`daten`, `wetter`, `auslegung`, `anker`, `hydraulik`).

---

## 1. Kernergebnis

| Frage | Ergebnis (indikativ, datenbasiert) |
|---|---|
| **F1:** Reicht das Netz bei Auslegungslast (−14 °C)? | Das KWK braucht **≈ 2,8–4,5 bar** Druckdifferenz, je nach Lastmodell. Bei linearer und unbegrenzter Last bestimmt der **Süden** die Anforderung, nicht die Mitte. Gerechnet ist mit gemessenem Rücklauf (120/59 °C), HW1 voll und PS1 wie 2025 maximal. Gegen den Planwert **4,0 bar** reicht das Netz **knapp oder nicht**. Gegen die aus der Pumpenförderhöhe ableitbaren **≈ 5,7 bar** reicht es mit Reserve (Abschnitt 6). |
| Was begrenzt heute an kalten Tagen? | Abschnitt 5. Drei Befunde: (1) Der **Süd-Schlechtpunkt** steht auf seinem Sollwert von ≈ 1,2 bar. (2) Die KWK-Δp ist **nicht frei bis 4,0 bar erhöhbar**. Jede bar KWK-Δp hebt die MVA-Δp um 0,8–1,0 bar, und bei laufender GT steht die MVA an ihrer Grenze (Planwert 7,5 bar, 2025 P99 8,2 bar). Im Kältebetrieb 2025 liegt die wirksame KWK-Grenze deshalb bei **≈ 3,6–4,3 bar**. (3) Der Betrieb **entlastet den Verbund**, indem er das Sekundärnetz West auf die HW2-Kessel umstellt (−8 MW Bezug). Bei den Kunden ist 2025 bis −5 °C kein Defizit messbar. 2020–2022 lag die Erzeugung an Tagen unter −5 °C dagegen **10–15 % unter dem unbegrenzten Bedarf**. |
| **F2:** Wie viel Ausbau ist ohne Maßnahmen möglich? | Bis 4,0 bar: **−5 % bis +25 %**, beim unbegrenzten Bedarf ≈ **0 %**. Bis ≈ 5,7 bar (Pumpe): **+12 % bis +48 %**. |
| Erzeugungsleistung | Die Verbund-Erzeugung nach Plan A bei −14 °C beträgt **251 MW**, mit KWK im Umleitbetrieb 267 MW. Sie reicht für das Tagesmittel, aber nicht für die **Stundenspitze** des unbegrenzten Bedarfs: An einem Auslegungstag fehlen ≈ 20–40 MW über 6–12 h, das sind **≈ 80–230 MWh** (Median P50/P90). Das ist eine **thermische** Speicheraufgabe. |
| Status 4,0 bar | Planwert. 2025 in 5 h überschritten (max. 4,16 bar). Die KWK-Pumpen (73,5 m) erlauben ≈ 5,7 bar am Austritt. Woraus 4,0 bar folgen, muss der Betreiber klären, z. B. aus der maximalen Δp der Kundenventile nahe dem KWK. **Von dieser Antwort hängen F1 und F2 am stärksten ab.** |
| Stärkste Stellhebel | **Ost-Vorlauf auf 120 °C** (heute ≈ 114 °C): weniger Ost-Massenstrom hebt die wirksame KWK-Grenze um ≈ 0,8 bar. **Rücklauf**: −5 K ≈ −0,5 bar, +5 K ≈ +0,8 bar. **HW1** im Süden: ≈ 1 bar je 100 kg/s. **West aus HW2-Kesseln** versorgen. |

Einschränkungen:
* Alle Aussagen beruhen auf **Ersatzgesetzen** aus dem Betriebsbereich 2025, nicht auf dem Netzmodell. Bei Auslegung wird bis zum 1,1- bis 1,45-fachen Massenstrom extrapoliert.
* Das Süd-Gesetz ist das **heutige Regelverhalten**. Ein anderer Sollwert am Schlechtpunkt verschiebt es.
* Die Aussagen sind deshalb **Plausibilitätsanker**, die das konsistente Netzmodell (Plan, Phase 2/3) reproduzieren muss.

---

## 2. Wetter Referenzstation und Auslegungstemperatur

Tiefste n-Tage-Mittel der Lufttemperatur je Jahr, 1991–2025:

| Dauer | Minimum | Jahr | 10-%-Quantil der Jahresminima | Median | Jahre < −10 °C |
|---|---|---|---|---|---|
| 1 Tag | −17,0 °C | 2012 | −14,5 °C | −10,2 °C | 19 |
| 2 Tage | −16,2 °C | 2012 | −13,9 °C | −9,0 °C | 14 |
| 3 Tage | −15,8 °C | 2012 | −12,7 °C | −8,1 °C | 11 |
| 5 Tage | −15,1 °C | 2012 | −11,4 °C | −7,1 °C | 9 |

* Ein **Tagesmittel von −14 °C** entspricht etwa einem **10-Jahres-Kältetag**. Ein 5-Tage-Mittel von −11 °C tritt ebenso etwa einmal in 10 Jahren auf. Das ist der Ansatz für die **Auslegungswoche** (Speicher-Mehrtagesbetrieb).
* Kältester Tag der Messjahre: **2025 nur −5,6 °C** (31.12.) – das Jahr war mild und deckt den Auslegungsfall nicht ab. 2021 erreichte −10,2 °C (12.02.).
* Der Basistag der Studie (14.02.2025) hatte nach DWD ein Tagesmittel von −1,5 °C; die Studie nennt −3,7 °C aus ihrer eigenen Temperaturreihe.

## 3. Heizkurve und Auslegungsspreizung

KWK-Vorlauftemperatur 2025 (Median) gegen DWD-Tagestemperatur:

| T_a-Klasse | −11 | −9 | −7 | −5 | −3 | −1 | +1 | +5 | +9 | +13 °C |
|---|---|---|---|---|---|---|---|---|---|---|
| VL gemessen | 121 | 123 | 118 | 115 | 113 | 111 | 110 | 102 | 96 | 95 °C |
| Vorgabe 110 − T_a (90…120) | 120 | 119 | 117 | 115 | 113 | 111 | 109 | 105 | 101 | 97 °C |
| RL gemessen | 59,4 | 59,6 | 59,0 | 58,9 | 58,9 | 58,7 | 58,7 | 58,9 | 60,1 | 62,5 °C |

* Mit DWD-Temperaturen folgt der Betrieb im Winter der **Vorgabe-Heizkurve**: ≈ 120 °C ab −10 °C.
* Der Rücklauf ist praktisch konstant bei ≈ 59 °C.
* Die Auslegungsspreizung am KWK beträgt damit **≈ 61 K** (120/59 °C). Die „107 °C“ in Plan A beziehen sich auf den Arbeitspunkt der Angabe „2350 t/h = 127 MW“ und sind nicht die Fahrweise. Das klärt Review N5.
* **Rücklauf aus Messdaten:** Bei Ta < −5 °C liegt der KWK-Rücklauf im Median bei **59,1 °C** (P90 59,9 °C). Mit 120 °C Vorlauf ergibt das **60,9 K** bzw. 60,1 K. Diese Werte gehen direkt in Abschnitt 6 ein, statt einer angenommenen Spreizung. Unterhalb +5 °C hängt der Rücklauf kaum von der Außentemperatur ab; die Extrapolation auf −14 °C ist daher unkritisch.
* Die Ost-Erzeuger fahren 2025 bei Kälte nur **≈ 109–115 °C** Vorlauf, Plan A sieht 125 °C vor. Ihr Massenstrom ist dadurch ≈ 10 % größer als nötig; das ist hydraulisch relevant (Abschnitt 5.2).

## 4. Auslegungslast

Regression der Tagesmittelleistung auf das Tagesmittel der Außentemperatur, Tage unter 12 °C, mit Wochenend-Term. „Ta_eff“ steht für 0,5·T + 0,3·T(−1 d) + 0,2·T(−2 d). Das Modell **linear unbegrenzt** wird nur auf Tagen ≥ 0 °C angepasst, mit zusätzlichem Term für die Ferienzeit 23.12.–06.01. Es beschreibt den Bedarf ohne hydraulische Begrenzung.

| Reihe | Modell | Steigung [MW/K] | σ [MW] | P50 bei −14 °C | P90 bei −14 °C |
|---|---|---|---|---|---|
| Lastgang 2020–2022 (Erzeugung gesamt) | linear | −6,6 | 12,3 | 223 MW | 239 MW |
| Lastgang 2020–2022 | quadratisch | | | 196 MW | 212 MW |
| Lastgang 2020–2022 | **linear unbegrenzt** | −7,1 | 12,3 | 231 MW | 247 MW |
| 2025 gesamt (korrigiert) | linear | −7,3 | 11,8 | 240 MW | 254 MW |
| 2025 gesamt | quadratisch | | | 222 MW | 237 MW |
| 2025 gesamt | **linear unbegrenzt** | −7,4 | 12,1 | 241 MW | 257 MW |
| 2025 Verbund (ohne HW2-Kessel) | linear | −6,6 | 12,1 | 223 MW | 238 MW |
| 2025 Verbund | quadratisch | | | 186 MW | 201 MW |
| 2025 Verbund | **linear unbegrenzt** | −7,0 | 12,4 | 230 MW | 246 MW |

**Abflachung an kalten Tagen.** Die Abweichung kalter Werktage vom unbegrenzten Bedarf ist ohne Ferienzeit gebildet; „Lastgang“ ist die Erzeugung gesamt.

| Reihe | T_a-Klasse | Tage | Abweichung |
|---|---|---|---|
| Lastgang 2020–2022 | < −8 °C | 2 | −30 MW (−15 %) |
| Lastgang 2020–2022 | −8 … −5 °C | 4 | −17 MW (−10 %) |
| Lastgang 2020–2022 | −5 … −2 °C | 17 | −2 MW (−2 %) |
| 2025 gesamt | −5 … −2 °C | 6 | +1 MW (0 %) |
| 2025 Verbund | −5 … −2 °C | 6 | −7 MW (−4 %) |

* Die Abflachung ist **kein Ferieneffekt**. Die Weihnachtszeit liegt eher über der Geraden.
* Sie tritt **unter ≈ −5 °C** auf. 2025 gab es keinen solchen Werktag (kältester Tag 31.12. mit −5,6 °C).
* 2025 ist das Verbund-Minus bei −5 … −2 °C **vollständig eine Verlagerung**: Der Bezug West über den WÜ sinkt um 8 MW, die HW2-Kessel liefern 7 MW mehr (Abschnitt 5.4).
* Das deckt sich mit der Betreiberaussage, dass die Hydraulik an kalten Tagen begrenzt. Der Lastgang unterschätzt dann den Bedarf. **Für die Auslegung gilt deshalb „linear unbegrenzt“**; das quadratische Modell beschreibt nur die heute begrenzte Lieferung.

Weitere Befunde:
* Die Lastgänge passen sehr eng zur lokalen Temperatur: r = −0,94 … −0,96 je Jahr. Der Lastgang 2020 läuft ab dem 01.01. fortlaufend durch, einschließlich 29.02.; das bestätigt die Korrelation.
* Das Niveau 2025 liegt bei gleicher Temperatur ≈ 6 % über 2020–2022 (Achsenabschnitt 138 gegen 130 MW). Das deutet auf Netzzuwachs hin; Jahresenergie 2025 ≈ 613 GWh, 2020–2022: 571–670 GWh.
* Das Verhältnis Stundenspitze zu Tagesmittel an Frosttagen liegt bei 1,14 (2025) bzw. 1,17 (2020–2022), P90 1,22–1,28.
* **Auslegungs-Stundenlast Verbund:** 212–229 MW (quadratisch, heute begrenzt) bis **262–280 MW** (linear unbegrenzt, P50–P90).

Die Studie nennt für den Basistag 215 MW Tagesmittel; mit den Daten ergeben sich ≈ 169 MW. Ihre Auslegungsangabe von 216 MW (Mittel) und 269 MW (Spitze) liegt im Band, entsteht in den Szenarien aber nicht: Dort bleibt die Last auf dem Basistag (Review 2.1).

## 5. Hydraulische Begrenzung bei Kälte

### 5.1 Welche Grenzen erreicht sind (2025, Anteil der Stunden)

| T_a | Stunden | Ost-Δp ≥ 7,0 bar | Ost-Δp ≥ 7,5 bar | KWK-Δp ≥ 3,5 bar | Süd ≤ 1,1 bar | Mitte ≤ 1,2 bar | GT in Betrieb | Ost-Δp P95 | KWK-Δp P95 |
|---|---|---|---|---|---|---|---|---|---|
| < −2 °C | 517 | 12 % | 5 % | 2 % | 41 % | 7 % | 60 % | 7,4 bar | 3,35 bar |
| −2 … 2 °C | 1 411 | 24 % | 11 % | 4 % | 29 % | 5 % | 61 % | 7,7 bar | 3,45 bar |
| 2 … 8 °C | 1 929 | 21 % | 12 % | 3 % | 19 % | 7 % | 43 % | 7,8 bar | 3,41 bar |
| > 8 °C | 4 799 | 7 % | 4 % | 0,3 % | 9 % | 5 % | 22 % | 7,3 bar | 2,83 bar |

Definitionen:
* Ost-Δp ist die höchste Austritts-Δp von MVA, GT (in Betrieb) und Bio-KWK. In 99 % der Stunden ist das die MVA.
* Süd ist das Minimum von V01 und V06; Mitte ist das Minimum der Mitte/City-Stationen.

Befunde:
* Das **KWK** erreicht weder seine 4,0 bar (P95 3,3–3,5 bar) noch seine thermischen Grenzen. Das Tagesmittel liegt bei höchstens 63 MW gegen 127 MW, der Durchfluss bei höchstens 1 000 t/h gegen 2 350 t/h.
* An der Grenze sind dagegen zwei andere Stellen:
  * der **Süd-Schlechtpunkt**: V01 ist praktisch konstant 1,2 bar, also regelungsnah; V06 liegt bei 1,1–1,3 bar;
  * die **Ost-Pumpen**: die MVA-Δp erreicht bei laufender GT bis 7,8 bar.
* Die Ost-Erzeuger laufen bei Kälte an ihrer thermischen Grenze: MVA ≈ 44 MW, GT 32–37 MW, Bio-KWK 14,5 MW.

### 5.2 Kopplung Ost ↔ KWK

Die Ost-Erzeuger speisen gegen die Druckdifferenz, die das KWK einstellt. Aus 8 354 h ergibt sich (ṁ in kg/s):

Δp_MVA − Δp_KWK = 0,56 + 0,301·(ṁ_Ost/100)² − 0,214·(ṁ_KWK/100)² bar  (R² 0,86, Restfehler P90 0,64 bar)

* Der erste Massenstrom-Term ist der Transportverlust Ost → Verbund. Der zweite ist die Entlastung durch den KWK-Strom bis zum Treffpunkt der Ströme.
* Stündliche Differenzen bestätigen den Durchgriff: **+0,78 bar MVA-Δp je bar KWK-Δp** (SE 0,01, mit Ost-, KWK- und HW1-Massenstrom als Regressoren). Mit strengerem Ausreißerfilter ergibt sich ≈ 0,96.
* Folge: **Die wirksame KWK-Grenze ist min(KWK-Grenze; MVA-Grenze − Ost-Verlust).**
* Auch die MVA-Grenze ist ein Planwert: 7,5 bar laut Plan A. 2025 wurde sie in 552 h überschritten (P99 8,2 bar, max. 9,0 bar). Aus der Nennförderhöhe 90 m folgen ≈ 7,9 bar.
* Im Kältebetrieb 2025 (Ta < −2 °C, GT in Betrieb, 293 h; ṁ_Ost ≈ 381 kg/s, ṁ_KWK ≈ 217 kg/s) ergibt das **≈ 3,6 bar** (MVA 7,5 bar) bzw. **≈ 4,3 bar** (MVA 8,2 bar). Gefahren wurden im Median 2,8 bar.
* **Hebel Ost-Vorlauf:** Bei 120 °C statt 114 °C sinkt ṁ_Ost bei gleicher Leistung auf ≈ 343 kg/s. Die wirksame KWK-Grenze steigt damit um ≈ 0,8 bar, auf **≈ 4,4–5,1 bar**.
* Ebenso wirkt es, Ost-Leistung zum KWK zu verschieben. An den kalten Tagen 17.–19.02.2025 lief die GT nicht: Die MVA-Δp lag nur bei 3,7 bar, KWK (60–63 MW) und HW1 (22 MW) übernahmen.

### 5.3 Schlechtpunktregelung Süd

In der Heizperiode (Ta < 8 °C, 3 799 h) folgt die KWK-Δp dem Gesetz (F = P/ΔT in MW/K):

Δp_KWK = 2,05 + 0,223·F² − 1,03·ṁ_HW1/100 − 0,42·Δp_PS1  (R² 0,65, Restfehler P90 0,48 bar)

* Das Gesetz beschreibt die **heutige Regelung** auf den Süd-Schlechtpunkt, vermutlich V01 (dessen Δp ist praktisch konstant).
* HW1 entlastet das KWK um ≈ 1 bar je 100 kg/s, PS1 um ≈ 0,4 bar je bar Pumpengewinn. Das passt zu den Netzhebeln (Abschnitt 7: V06 +1,0 bar je 100 kg/s HW1).
* Für die Mitte-Stationen gilt das Verlustgesetz aus Abschnitt 6. Bei hoher Last ist **der Süden** die strengere Anforderung, selbst mit voller HW1-Unterstützung.

### 5.4 Versorgung an kalten Werktagen 2025

Abweichung vom unbegrenzten Bedarf (Fit ≥ 0 °C) an 6 Werktagen mit Ta < −2 °C, außerhalb der Ferienzeit:

| | V05 (Süd) | V14 (Süd) | V07 (Ost-L7) | V22 (S) | V13 (West) | Verbund | gesamt | WÜ Verbund → West | Kessel West (HW2) |
|---|---|---|---|---|---|---|---|---|---|
| Abweichung | +6 % | +1 % | +2 % | +17 % | +6 % | −4 % (−6,5 MW) | 0 % | −44 % (−7,9 MW) | +108 % (+7,4 MW) |

* Die Kunden wurden 2025 bei −2 … −5 °C voll versorgt.
* Der Verbund wurde entlastet, indem das Sekundärnetz West auf die HW2-Kessel umgestellt wurde. Die HW2-Kessel lieferten 2025 höchstens 23 von 40 MW; hier liegt weitere Entlastung.

### 5.5 Mechanismus der Begrenzung

Die Begrenzung an kalten Tagen ist **keine fehlende KWK-Förderhöhe**, sondern das Zusammenspiel dreier Größen:
1. **Süd-Schlechtpunkt auf Sollwert:** Er bestimmt die KWK-Δp, zusammen mit HW1 und PS1.
2. **Ost-Pumpengrenze:** Weil die Ost-Erzeuger ≈ 1:1 an die KWK-Δp gekoppelt sind, kann das KWK nicht frei nachschieben, solange Ost mit niedrigem Vorlauf und vollem Massenstrom einspeist. Die wirksame Grenze liegt bei ≈ 3,6–4,3 bar statt 4,0 bar; welcher Wert gilt, hängt an der MVA-Grenze (7,5 bar Planwert oder mehr).
3. **Ausweichen im Betrieb:**
   * HW1 einsetzen,
   * West auf HW2 umstellen,
   * an einzelnen Tagen ohne GT fahren.

Unter ≈ −5 °C reichen diese Maßnahmen nach den Lastgängen 2020–2022 nicht mehr: Die Erzeugung liegt dort 10–15 % unter dem Bedarf (Abschnitt 4).

## 6. Erforderliche KWK-Druckdifferenz und Grenzband

**Mitte-Gesetz.** Aus 7 818 Stunden 2025 angepasst:

Δp_KWK − min Δp_Mitte = a + b·(P/ΔT)², mit a = 0,118 bar und b = 0,1405 bar/(MW/K)².

* P/ΔT ist proportional zum Massenstrom; P ist die Verbundeinspeisung, ΔT die KWK-Spreizung.
* Bestimmtheitsmaß R² = 0,76; Restfehler P90 0,28 bar.
* Mitte-Stationen: V03, V10, V12, V23, V24; gefordert sind 1,0 bar.

**Süd-Gesetz.** Siehe Abschnitt 5.3. Bei Auslegung wird HW1 voll angesetzt (40 MW, 153 kg/s) und PS1 mit 1,7 bar Gewinn (P99 2025).

**Grenzband KWK-Δp** (die 4,0 bar sind nicht gesichert hart):

| Grenze | Wert | Herkunft |
|---|---|---|
| Planwert | 4,0 bar | Plan A, Austritt KWK; Status offen |
| gemessen 2025 | max. 4,16 bar | 5 h über 4,0 bar, ohne bekannte Störung |
| Pumpe | ≈ 5,7 bar | 73,5 m Förderhöhe bei 120 °C (6,8 bar) minus 1,1 bar anlageninterne Verluste |
| Ost-Kopplung | ≈ 3,6–4,3 bar (Kältebetrieb 2025, MVA 7,5–8,2 bar) bzw. ≥ 5,4 bar (Auslegung, Ost 84 MW mit 120 °C, MVA 7,5 bar) | Abschnitt 5.2; die Entlastung durch den KWK-Strom ist konservativ nicht über das P99 2025 hinaus extrapoliert |

**Auslegungsfall.** Annahmen:
* T_a −14 °C, Vorlauf 120 °C, **Rücklauf gemessen 59,1 °C (ΔT 60,9 K)**;
* Ost 84 MW (Plan A: MVA 40, GT 31, Bio-KWK 13), HW1 40 MW, Stunden-Spitzenfaktor 1,14.

| Lastmodell (Verbund, Stunde) | P | P_KWK | erf. Δp Mitte | erf. Δp Süd | maßgebend | Reserve bis 4,0 bar | Reserve bis 5,7 bar | Extrapolation F |
|---|---|---|---|---|---|---|---|---|
| quadratisch P50 | 212 MW | 88 MW | 2,82 bar | 2,47 bar | 2,82 bar | +25 % | +48 % | 1,09 |
| quadratisch P90 | 229 MW | 105 MW | 3,11 bar | 2,93 bar | 3,11 bar | +16 % | +37 % | 1,18 |
| linear P50 | 253 MW | 129 MW | 3,55 bar | 3,63 bar | 3,63 bar | +5 % | +24 % | 1,30 |
| linear P90 | 271 MW | 147 MW | 3,90 bar | 4,19 bar | 4,19 bar | −2 % | +16 % | 1,40 |
| **linear unbegrenzt P50** | **262 MW** | 138 MW | 3,72 bar | 3,90 bar | **3,90 bar** | **+1 %** | **+20 %** | 1,35 |
| linear unbegrenzt P90 | 280 MW | 156 MW | 4,09 bar | 4,49 bar | 4,49 bar | −5 % | +12 % | 1,44 |

Erläuterungen:
* „Reserve“ ist der Lastzuwachs, bis die maßgebende Anforderung (Mitte oder Süd) die Grenze erreicht.
* „Extrapolation F“ ist der Massenstrom relativ zum P99 der Messungen, auf denen das Süd-Gesetz beruht.

**Rücklauf-Sensitivität** (linear unbegrenzt P50, 262 MW):

| Rücklauf | ΔT | erf. KWK-Δp | Reserve bis 4,0 bar | Reserve bis 5,7 bar |
|---|---|---|---|---|
| gemessen, Median Ta < −5 °C: 59,1 °C | 60,9 K | 3,90 bar | +1 % | +20 % |
| gemessen, P90: 59,9 °C | 60,1 K | 4,01 bar | 0 % | +18 % |
| Median + 5 K | 55,9 K | 4,68 bar | −7 % | +10 % |
| Median − 5 K | 65,9 K | 3,39 bar | +8 % | +29 % |

**Erzeugungsleistung am Auslegungstag.** Die Verbund-Erzeugung nach Plan A bei −14 °C beträgt 251 MW (KWK 127, MVA 40, GT 31, Bio-KWK 13, HW1 40). Mit KWK im Umleitbetrieb (143 MW) sind es 267 MW. Gerechnet sind die 22 Werktagsprofile unter −2 °C aus den Lastgängen 2020–2022, skaliert auf das Auslegungs-Tagesmittel:

| Tagesmittel (Verbund) | Erzeugung | fehlende Leistung, Median / P90 | Stunden | fehlende Energie, Median / P90 |
|---|---|---|---|---|
| linear P50, 223 MW | 251 MW | 12 / 20 MW | 4 | 33 / 62 MWh |
| linear P90, 238 MW | 251 MW | 30 / 39 MW | 8 | 135 / 181 MWh |
| **linear unbegrenzt P50, 230 MW** | 251 MW | **21 / 29 MW** | 6 | **80 / 113 MWh** |
| linear unbegrenzt P90, 246 MW | 251 MW | 40 / 49 MW | 12 | 233 / 278 MWh |
| linear unbegrenzt P50, 230 MW | 267 MW | 5 / 13 MW | 2 | 10 / 30 MWh |
| linear unbegrenzt P90, 246 MW | 267 MW | 24 / 33 MW | 6 | 93 / 130 MWh |

* Beim quadratischen Modell fehlt keine Leistung.
* Ein Teil der Lücke lässt sich mit voller HW2-Leistung im Westen und dem HW2-Export (9 MW) schließen.
* Zu klären ist, ob die Plan-A-Leistungen bereits den n−1-Fall abbilden. 2025 lieferte Ost bei Kälte ≈ 92 MW statt 84 MW.

Zum Vergleich gemessen 2025:
* KWK-Δp in Hochlast: P95 3,5 bar, Maximum 4,16 bar.
* Massenstrom-Äquivalent F_max 3,60 MW/K.

## 7. Netzhebel (Validierungsziele, mit korrigierter Last)

Regression auf stündliche Differenzen, n ≈ 5 000 h. Die Spalten geben an, um wie viel bar sich der Kunden-Δp ändert.

| Station | je 100 kg/s HW1 | je bar KWK-Δp | je bar MVA-Δp | je 10 MW Last | je bar PS1-Gewinn |
|---|---|---|---|---|---|
| V06 (Süd) | +1,02 | 0,66 | 0,04 | −0,18 | +0,33 |
| City (V03, V10, V24) | +0,17…0,20 | 0,82 | 0,10 | −0,12…−0,14 | −0,06…−0,07 |
| V12 (L4) | +0,19 | 0,82 | 0,09 | −0,15 | −0,06 |
| V23 (L1) | +0,20 | 0,83 | 0,09 | −0,15 | −0,04 |
| V22 | +0,09 | 0,73 | 0,22 | −0,09 | −0,04 |
| V15 (Mitte-L3) | +0,09 | 0,72 | 0,23 | −0,09 | −0,05 |
| HW2-Prim | +0,37 | 0,73 | 0,03 | −0,16 | +0,02 |

* Gegenüber der ersten Auswertung (Review 9.2, N4, mit fehlerhaftem GT-Signal in der Last) ändern sich die City-Hebel für HW1 (+0,07…0,12 → +0,17…0,20) und MVA (0,03…0,05 → 0,09…0,10).
* Robust sind: V06 ≈ +1 bar je 100 kg/s HW1, KWK-Durchgriff 0,72–0,83, PS1-Wirkung im Süden positiv und upstream negativ.
* Als Validierungsziel gilt daher eine **Spanne**: City +0,07…0,20 bar je 100 kg/s lokale Süd-Einspeisung.

## 8. Temperatur-Tracer (Ost-Wasseranteil, Winter, n = 287 h)

| Station | V22 | V11 | V15 | V23 | V17 (City) | V12 | V24 | V05 |
|---|---|---|---|---|---|---|---|---|
| Ost-Anteil | 0,75 | 0,85 | 0,64 | 0,49 | 0,28 | 0,31 | 0,09 | 0,14 |
| R² | 0,63 | 0,65 | 0,51 | 0,48 | 0,28 | 0,15 | 0,11 | 0,09 |

Aussagekräftig ist der Tracer nur bei R² ≳ 0,3. Mit 15-min-Werten wird er deutlich schärfer.

## 9. Signalprüfungen

* **Identische Signale:** nur `gas_turbine_heat` = `boiler_plant_2_secondary_heat` (8 757 h).
* **GT-Wärme korrigiert:**

  | Quelle | Anteil der Stunden |
  |---|---|
  | gemessen (V̇·Δh) | 34,8 % |
  | Stillstand (T_VL < 60 °C) | 26,7 % |
  | imputiert über Δp und ΔT (R² = 0,76) | 38,4 % |

* **Einheitentest** (Verhältnis gemessen zu berechnet; 1,00 = passende Einheit):

  | Station | t/h | m³/h im RL | m³/h im VL |
  |---|---|---|---|
  | V07 | 0,999 | 1,01 | 1,04 |
  | V22 | 0,998 | 1,01 | 1,05 |
  | V14 | 0,997 | 1,02 | 1,04 |
  | V05 | 0,999 | 1,01 | 1,04 |
  | HW2-Prim | 0,999 | 1,02 | 1,04 |
  | Bio-KWK | 0,96 | 0,98 | **1,00** |

  Kundenstationen messen also in t/h, das Bio-KWK in m³/h im Vorlauf.

## 10. Folgerungen für Studie und Plan

1. **Auslegungsfall neu definieren:**
   * −14 °C Tagesmittel mit dem **unbegrenzten** Bedarf: Verbund 262–280 MW Stundenlast; das quadratische Modell nur als „heutige begrenzte Lieferung“;
   * Spreizung aus Messdaten 120/59 °C (Abschnitt 3);
   * zusätzlich eine Auslegungswoche mit 5-Tage-Mittel ≈ −11 °C.
2. **Hauptkennzahl** ist die erforderliche KWK-Δp, und zwar das Maximum aus Mitte- und Süd-Anforderung. Sie wird gegen ein **Grenzband** geprüft: 4,0 bar Planwert, ≈ 5,7 bar Pumpe und die **Ost-Kopplung**, also die MVA-Δp unter ihrer Grenze (7,5 bar Planwert, 2025 bis 8,2 bar). Ein Δp-Defizit bei festgehaltenen Drücken ist keine geeignete Kennzahl. Das Netzmodell (Plan, Phase 2) muss die Ost-Kopplung als Validierungsziel reproduzieren.
3. **Entscheidende Betreiberangaben:**
   * Woraus folgen die 4,0 bar am KWK-Austritt und die 7,5 bar an der MVA: Kundenventile, Druckstufe, Erfahrungswert? **Pumpenkennlinien** von KWK und MVA anfordern; beide Grenzen wurden 2025 überschritten.
   * Wo liegt die Schlechtpunktregelung, mit welchem Sollwert? Vermutet: V01, 1,2 bar. Welche Mindest-Δp brauchen V01 und V06 tatsächlich?
   * Warum fahren MVA und GT mit ≈ 114 °C statt 125 °C (Plan A), und lässt sich das anheben?
   * Kann das Sekundärnetz West bei Auslegung vollständig aus HW2 versorgt werden?
   * Gab es 2021/2022 an Tagen unter −5 °C Unterversorgung bei Kunden?
   * Bilden die Plan-A-Leistungen den n−1-Fall ab?
4. **Speicher – zwei getrennte Nutzen:**
   * **Hydraulisch:** Entlastung ≈ 0,1–0,3 bar KWK-Δp, also ≈ 2–6 Prozentpunkte Ausbaureserve, wenn der Hebel am V22 ähnlich wirkt wie im Süden. Am Standort S (Ost-L5, 75 % Ost-Wasser) wirkt der Speicher zusätzlich auf die **Ost-Kopplung**: Eine Entladung dort kann den Ost-Transport entlasten oder verdrängen. Das ist im Netzmodell und per Feldtest zu prüfen (Plan 3.3).
   * **Thermisch:** Am Auslegungstag fehlen ≈ 20–40 MW über 6–12 h, also **≈ 80–230 MWh** (Abschnitt 6). Diese Spitzendeckung ist voraussichtlich der **größere Nutzen**. Ein 40-MW-Speicher passt in der Leistung dazu.
5. **Alternativen mit gleicher oder höherer Wirkung,** im Maßnahmenvergleich zu rechnen:
   * **Ost-Vorlauf 120 °C:** wirksame KWK-Grenze ≈ +0,8 bar, ohne Investition;
   * **Rücklauf −5 K:** ≈ −0,5 bar erforderliche Δp;
   * **HW1 und PS1 im Süden:** ≈ 1 bar je 100 kg/s HW1;
   * **West aus HW2-Kesseln;**
   * Druckerhöhungsstation im Süden.
