# Datenanalyse DHN-A: Wetter, Auslegungslast und erforderliche KWK-Druckdifferenz

> **Anonymisierung:** Netz „DHN-A“. Verbraucher V01–V24; die Zuordnung zu den Klarnamen liegt nur lokal beim Auftraggeber. Erzeuger nach Typ:
> * KWK = Gas-KWK-Hauptanlage und Druckhalter
> * MVA = Abfallverbrennung
> * GT = Gasturbine
> * Bio-KWK = Biomasse-KWK
> * HW1/HW2 = Heizwerke; HW2 mit Wärmeübertrager zum Sekundärnetz West
> * PS1/PS2 = Pumpstationen
>
> Weitere Bezeichnungen: Speicherstandort **S = Verbraucher V22**; L1–L7 = Haupt- und Transportleitungen; N_… = Modellknoten; A1… = Armaturen; Plan A/B/C = Betreiberpläne (Erzeuger, Netz Mitte, Netz West). Datensatz und Spaltennamen: `data/dhn_a/README.md`.

Stand: 2026-10-01 · Bezug: `Plan_belastbare_Aussagen.md` (Arbeitspakete 1.8–1.11, 3.2, 3.5, 3.6, 4.1) und `Review_Speicherstudie.md` (Abschnitt 9).

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
Laufzeit ≈ 5 s. Die Ergebnisse stehen unter `results/dhn_study/datenanalyse/` (CSV und `zusammenfassung.md`). Der Code liegt in `scripts/dhn_study/` (`daten`, `wetter`, `auslegung`, `anker`).

---

## 1. Kernergebnis

| Frage | Ergebnis (indikativ, datenbasiert) |
|---|---|
| **F1:** Reicht das Netz bei Auslegungslast (−14 °C)? | Für die Mitte/City-Stationen braucht das KWK **≈ 2,8–3,9 bar** Druckdifferenz (Spreizung 120/59 °C). Die Planangabe für den KWK-Austritt ist **4,0 bar**. Damit ist das Netz **knapp ausreichend**, mit **0,1–1,2 bar Reserve**. Steigt der Rücklauf um 6 K, sind es 3,2–4,5 bar und die Grenze kann überschritten werden. |
| **F2:** Wie viel Ausbau ist ohne Maßnahmen möglich? | Bis die KWK-Δp 4,0 bar erreicht: **≈ +2 % bis +30 %** (zentral ≈ +9…20 %), bezogen auf die Auslegungslast. Voraussetzung: gleiche räumliche Verteilung, Ost-Erzeuger an ihrer Grenze wie 2025. |
| Vergleich mit der Studie | Die Größenordnung „Ausbau ≈ +5…10 %“ der Studie ist **nicht abwegig**. Ihre Herleitung ist aber falsch: Nicht die pauschal verschlechterten Erzeugerdrücke (S-05) begrenzen, sondern die **KWK-Druckdifferenz bei Auslegungslast**. Der Bestand ist bei Last 2025 nicht kritisch, bei Auslegungslast knapp. |
| Stärkste Stellhebel | **Rücklauftemperatur** (6 K entsprechen ≈ 0,4–0,6 bar), **Status der 4,0-bar-Grenze**, **Auslegungslast** (linear oder abflachend) |

Einschränkungen:
* Die Ergebnisse beruhen auf einem datenbasierten Verlustgesetz (Abschnitt 4), nicht auf dem Netzmodell.
* Sie gelten für die Mitte/City-Stationen mit Δp_min 1,0 bzw. 1,2 bar. Der Süden (V06) hängt zusätzlich an PS1 und HW1.
* Die Auslegung liegt bis zum 1,23-fachen des 2025 gemessenen Massenstroms; das ist eine Extrapolation.

Die Aussagen sind deshalb als **Plausibilitätsanker** zu verstehen, den das konsistente Netzmodell (Plan, Phase 2/3) reproduzieren muss.

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

## 4. Auslegungslast

Regression der Tagesmittelleistung auf das Tagesmittel der Außentemperatur, Tage unter 12 °C, mit Wochenend-Term. „Ta_eff“ steht für 0,5·T + 0,3·T(−1 d) + 0,2·T(−2 d).

| Reihe | Modell | Steigung [MW/K] | σ [MW] | Residuum kalte Tage | P50 bei −14 °C | P90 bei −14 °C |
|---|---|---|---|---|---|---|
| Lastgang 2020–2022 (Erzeugung gesamt) | linear | −6,6 | 12,3 | −8,2 MW | 223 MW | 239 MW |
| Lastgang 2020–2022 | quadratisch | | | −1,5 MW | 196 MW | 212 MW |
| 2025 gesamt (korrigiert) | linear | −7,3 | 11,8 | −6,1 MW | 240 MW | 254 MW |
| 2025 gesamt | quadratisch | | | −3,6 MW | 222 MW | 237 MW |
| 2025 Verbund (ohne HW2-Kessel) | linear | −6,6 | 12,1 | −8,9 MW | 223 MW | 238 MW |
| 2025 Verbund | quadratisch | | | −3,4 MW | 186 MW | 201 MW |

* Die Lastgänge passen sehr eng zur lokale Temperatur: r = −0,94 … −0,96 je Jahr. Der Lastgang 2020 läuft ab dem 01.01. fortlaufend durch, einschließlich 29.02.; das bestätigt die Korrelation.
* An kalten Tagen liegt die Last **unter der Geraden** (Residuum −6 … −12 MW). Ein Beispiel ist der 12.02.2021 mit −10,2 °C und nur 174 MW Tagesmittel. Deshalb werden lineares und quadratisches Modell als **Band** geführt.
* Die Ursache ist offen: gesättigte Kundenanlagen, Verhalten oder auch bereits hydraulische Begrenzung. Das ist mit dem Betreiber zu klären, denn im letzten Fall unterschätzt der Lastgang den Bedarf.
* Das Niveau 2025 liegt bei gleicher Temperatur ≈ 6 % über 2020–2022 (Achsenabschnitt 138 gegen 130 MW). Das deutet auf Netzzuwachs hin; Jahresenergie 2025 ≈ 613 GWh, 2020–2022: 571–670 GWh.
* Das Verhältnis Stundenspitze zu Tagesmittel an Frosttagen liegt bei 1,14 (2025) bzw. 1,17 (2020–2022), P90 1,22–1,28.
* **Auslegungs-Stundenlast Verbund: ≈ 212–271 MW**, gesamt (mit HW2-Kesseln) ≈ 250–290 MW.

Die Studie nennt für den Basistag 215 MW Tagesmittel; mit den Daten ergeben sich ≈ 169 MW. Ihre Auslegungsangabe von 216 MW (Mittel) und 269 MW (Spitze) liegt im Band, entsteht in den Szenarien aber nicht: Dort bleibt die Last auf dem Basistag (Review 2.1).

## 5. Erforderliche KWK-Druckdifferenz

Das Verlustgesetz wird aus 7 818 Stunden 2025 angepasst:

Δp_KWK − min Δp_Mitte = a + b·(P/ΔT)², mit a = 0,118 bar und b = 0,1405 bar/(MW/K)².

* P/ΔT ist proportional zum Massenstrom; P ist die Verbundeinspeisung, ΔT die KWK-Spreizung.
* Bestimmtheitsmaß R² = 0,76; Restfehler P90 0,28 bar.
* Mitte-Stationen: V03, V10, V12, V23, V24

| Auslegungslast (Verbund, Stunde) | ΔT | erf. KWK-Δp für 1,0 bar | für 1,2 bar | Reserve bis 4,0 bar (1,0 bar) |
|---|---|---|---|---|
| quadratisch P50, 212 MW | 61 K | 2,81 bar | 3,01 bar | +30 % |
| quadratisch P90, 229 MW | 61 K | 3,10 bar | 3,30 bar | +21 % |
| linear P50, 253 MW | 61 K | 3,54 bar | 3,74 bar | +9 % |
| linear P90, 271 MW | 61 K | 3,89 bar | 4,09 bar | +2 % |
| linear P50, 253 MW | 55 K (RL +6 K) | 4,10 bar | 4,30 bar | −2 % |
| linear P90, 271 MW | 55 K | 4,53 bar | 4,73 bar | −8 % |

Zum Vergleich gemessen 2025:
* KWK-Δp in Hochlast: P95 3,2–3,5 bar, Maximum 4,16 bar.
* Massenstrom-Äquivalent F_max 3,60 MW/K. Die Auslegungsfälle liegen beim 0,97- bis 1,23-fachen.

## 6. Netzhebel (Validierungsziele, mit korrigierter Last)

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

## 7. Temperatur-Tracer (Ost-Wasseranteil, Winter, n = 287 h)

| Station | V22 | V11 | V15 | V23 | V17 (City) | V12 | V24 | V05 |
|---|---|---|---|---|---|---|---|---|
| Ost-Anteil | 0,75 | 0,85 | 0,64 | 0,49 | 0,28 | 0,31 | 0,09 | 0,14 |
| R² | 0,63 | 0,65 | 0,51 | 0,48 | 0,28 | 0,15 | 0,11 | 0,09 |

Aussagekräftig ist der Tracer nur bei R² ≳ 0,3. Mit 15-min-Werten wird er deutlich schärfer.

## 8. Signalprüfungen

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

## 9. Folgerungen für Studie und Plan

1. **Auslegungsfall neu definieren:**
   * −14 °C Tagesmittel mit Lastband 212–271 MW Verbund-Stundenlast,
   * Spreizung 120/59 °C,
   * zusätzlich eine Auslegungswoche mit 5-Tage-Mittel ≈ −11 °C.
2. **Hauptkennzahl** ist die erforderliche KWK-Δp gegen 4,0 bar, nicht ein Δp-Defizit bei festgehaltenen Drücken.
3. **Entscheidende Betreiberangaben:**
   * Ist 4,0 bar eine harte Grenze?
   * Ist die Abflachung der Last an kalten Tagen hydraulisch bedingt?
   * Welche Rücklauftemperatur ist bei Auslegung zu erwarten?
4. **Speicher:** Sein Nutzen ist am besten als **eingesparte KWK-Δp** bzw. **zusätzliche Ausbaureserve** auszudrücken. Mit dem City-Hebel von +0,07…0,20 bar je 100 kg/s und 40 MW (≈ 150 kg/s) ergibt sich größenordnungsmäßig **0,1–0,3 bar** Entlastung. Das entspricht ≈ 2–6 Prozentpunkten Ausbaureserve (erforderliche Δp steigt um ≈ 0,05 bar je Prozent Lastzuwachs), sofern der Hebel am V22 ähnlich wirkt wie im Süden; das ist per Feldtest zu prüfen (Plan 3.3).
5. **Alternativen mit gleicher oder höherer Wirkung**, im Maßnahmenvergleich zu rechnen:
   * Rücklauftemperatur um 5 K absenken (≈ 0,25–0,4 bar),
   * PS1 stärker fahren (Süden),
   * Druckerhöhungsstation.
