# Kraftwerkseinsatz 2025 – gemessener Betrieb vs. MILP-optimiert (DHN-A, ohne Speicher, ohne Prosumer)

Skript: `scripts/dhn_study/central_tes/dispatch_comparison.py`, Konfiguration `configs/central_tes/base.yaml` (unverändert).
Ergebnisse: `results/central_tes/dispatch_comparison/` (gitignored, enthält partnerabgeleitete Zeitreihen). An den
bestehenden Studienergebnissen und an der Paper-Pipeline ist nichts geändert.

```
python -m scripts.dhn_study.central_tes.dispatch_comparison --uc-sets ist prozent   # ≈ 6 min, 2 Kerne
python -m scripts.dhn_study.central_tes.dispatch_comparison --uc-wiederverwenden    # nur neu bewerten (≈ 1 min)
```

## Kernzahlen

| # | Kennzahl | Wert |
|---|---|---|
| 1 | IST 2025, bewertet mit der Kostenfunktion des MILP | **18,97 M€/a** (Brennstoff 27,13 · CO2 6,27 · Energiesteuer 0,21 · Stromerlös −14,63) |
| 2 | Studien-MILP F000, Mode H, Kalibrierung A | **15,71 M€/a = −3,27 M€/a (−17,2 %)**; Mode H kostet 21 € mehr als Mode E |
| 3 | davon MVA-Abnahme über dem gemessenen Wert | +32 GWh MVA-Wärme, davon 5,7 GWh in 348 h ohne MVA-Lieferung (v. a. Revision im September). Fährt die MVA wie gemessen, bleiben **−1,43 M€/a (−7,5 %)** |
| 4 | KWK-Δp-Grenze 4,0 bar abzüglich Betriebsreserve (Modellgrenze 3,36 bar) | kostet nur 5 k€/a. Das Studien-MILP überschreitet 4,0 bar in 30 h (max. 6,0 bar), IST gemessen in 5 h (max. 4,16 bar) |
| 5 | MILP mit Mindestlasten (P5 IST) und Anfahrkosten (fairster Vergleich) | **−1,12 M€/a (−5,9 %)** Betriebskosten; inkl. gleich bewerteter Anfahrkosten **−1,56 M€/a**. Mit Mindestlasten 30/50/10 %: −0,42 bzw. −0,47 M€/a |
| 6 | Wo der verbleibende Vorteil liegt (IST → MILP_UC) | GT nach Strompreis −0,65 M€ · mehr GT statt KWK −0,30 M€ · weniger HW1 −0,23 M€; 78 % der Differenz fallen in Stunden > 100 €/MWh |
| 7 | Erzielter GT-Strompreis · HW1-Wärme | IST 116,6 → MILP_UC 125,8 €/MWh (Studien-MILP 135,4) · HW1 35,7 → 19,9 GWh/a (3 610 → 2 216 Betriebsstunden) |
| 8 | Wärmegeführte Regel ohne Preissignal (BIO → MVA → KWK → GT → HW1) | **19,43 M€/a, +0,46 M€/a teurer als IST**: Der heutige Betrieb nutzt bereits Strompreissignale und holt rund 29 % des Abstands Regel → MILP_UC (0,46 von 1,58 M€/a) |

Kurz gefasst: Von den 3,27 M€/a, die das Studien-MILP gegenüber dem gemessenen Betrieb zeigt, sind gut die Hälfte (1,84 M€/a)
eine Folge der optimistischen MVA-Verfügbarkeit (Monats-P95) und kein Einsatzpotenzial. Weitere 0,30 M€/a verschwinden mit
Mindestlasten und Anfahrkosten. Der belastbare Rest beträgt **≈ 1,1 M€/a (6 %)** bei Mindestlasten wie gemessen,
mit den pauschalen 30/50/10 % nur ≈ 0,4 M€/a. Er stammt fast vollständig aus der strompreisorientierten
Fahrweise von GT und KWK und aus weniger HW1-Wärme.

## Fahrpläne

Alle Fahrpläne ohne Speicher und ohne Partner A/B (F000), stündlich 2025 (8 759 h), Last `D` wie in der Studie.

| Fahrplan | Beschreibung |
|---|---|
| `IST` | gemessene Wärme `Q_meas_*` wie `Hydro._sched_measured`: fehlende Werte = 0, die KWK schließt die Bilanz zur Last |
| `MILP_E`, `MILP_H` | Studie F000, perfekte Voraussicht, LP; Mode H mit Kalibrierung A (1 Iteration, 3 Schnitte) |
| `MILP_E_MVA_IST` | wie MILP_E, MVA aber fest wie gemessen (Abnahme abfallgeführt, nicht frei bis Monats-P95); nur nach unten, wenn die Last nach BIO kleiner ist |
| `MILP_H_MVA_IST_KWKGRENZE` | zusätzlich KWK-Δp-Modellbedarf ≤ 4,0 bar − 0,64 bar Betriebsreserve = 3,36 bar, harte Grenze in Mode H (2 Iterationen, 123 Schnitte) |
| `MILP_UC` | zusätzlich Binärvariablen für KWK, GT, HW1: Mindestlast = P5 der IST-Last in Betriebsstunden (11,8 / 4,9 / 2,4 MW), Anfahrkosten 5 / 2 / 0,2 k€ je Start; Mode-H-Iteration gegen dieselbe KWK-Grenze (1 Iteration, 124 Schnitte); HiGHS optimal, Gap < 10⁻¹² |
| `MILP_UC_PROZENT` | wie MILP_UC mit Mindestlasten 30 / 50 / 10 % der Kapazität (38,1 / 17,5 / 4,0 MW) |
| `REGEL` | feste Merit-Order ohne Strompreis: BIO must-run → MVA → KWK → GT → HW1, in den Grenzen von MILP_E_MVA_IST (inkl. Ost-Parallelgrenze) |

## Methode

**Gleiche Kostenfunktion.** Jeder Fahrplan wird stündlich mit `milp.plant_costs` bewertet, also genau mit der
Zielfunktion des MILP: c = (Brennstoffpreis + Energiesteuer + ef · 72 €/t) / η_th − η_el/η_th · λ_DayAhead. Gas kostet
48 €/MWh, Biomasse 20 €/MWh, die MVA-Übernahme 10 €/MWh_th. Energiesteuer fällt nur für HW1 an (5,5 €/MWh). Der Strom
wird zum Day-Ahead-Preis DE-LU 2025 gutgeschrieben, 15-min-Werte ab 01.10.2025 als Stundenmittel. Für die MILP-Fahrpläne
stimmt diese Bewertung auf < 1 € mit der Zielfunktion überein (Assertion im Skript, Test
`test_dispatch_comparison_gleiche_bewertung_regel_uc`).

**Was nicht zu den Betriebskosten zählt.** Pumpenstrom ist nicht Teil des MILP und wird nur berichtet. Die
Anfahrkosten werden für **alle** Fahrpläne gleich bewertet: Start = Übergang von ≤ 1 MW auf > 1 MW, beim UC aus den
Startvariablen. Sie stehen in einer eigenen Spalte, weil die LP-Fahrpläne sehr viele Starts haben. Die Strafe für
Notkühlung (10 000 €/MWh, nur UC) wird ausgewiesen, aber nicht zu den Kosten gezählt. Der Brennstoff der weggekühlten
Wärme ist in den Betriebskosten enthalten.

**Strom aus Wärme.** Der Strom der KWK-Anlagen ist Wärme · η_el/η_th wie im Modell. Gemessene Stromwerte liegen in
den Eingangsdaten nicht vor; eine Gegenüberstellung war daher nicht möglich.

**Zerlegung (Wasserfall).** Die Kostendifferenz A → B wird je Anlage in einen Mengen- und einen Zeitpunkteffekt
zerlegt. Der Mengeneffekt ist die Mengenänderung · (mittlere Grenzkosten der Anlage in A − mittlere Grenzkosten der KWK
in A). Die KWK ist die Ausgleichsanlage, ein Bilanzterm erfasst eine abweichende Gesamtmenge. Der Zeitpunkteffekt ist der
Rest der Kostenänderung der Anlage: andere Stunden zu anderen Strompreisen bei gleicher Menge. Die Zerlegung ist exakt
additiv (Assertion); die Kategorien a)–d) fassen diese Terme zusammen.

**Fairness-Treppe.** Ausgehend vom Studien-MILP werden die Freiheiten, die der reale Betrieb nicht hat, schrittweise
entzogen: MVA wie gemessen → KWK-Δp-Erfahrungswert → Mindestlasten und Anfahrkosten. Jede Stufe enthält die vorherigen.

## Ergebnisse

### Fairness-Treppe (`fairness.csv`)

| Stufe | Kosten [M€/a] | Δ zu IST [M€/a] | Δ zur Vorstufe [M€/a] | Rest des Studienvorteils | Anfahrkosten bewertet [M€/a] | Δ zu IST inkl. Anfahrkosten [M€/a] |
|---|---:|---:|---:|---:|---:|---:|
| IST (gemessen) | 18,97 | – | – | – | 0,64 | – |
| MILP F000 Mode H (Studie) | 15,71 | −3,27 | −3,27 | 100 % | 2,02 | −1,89 |
| + MVA fest wie gemessen | 17,55 | −1,43 | +1,84 | 44 % | 2,44 | +0,37 |
| + KWK-Δp ≤ 4,0 bar inkl. Betriebsreserve (Mode H) | 17,55 | −1,42 | +0,01 | 43 % | 2,44 | +0,38 |
| + Mindestlasten (P5 IST) und Anfahrkosten | 17,85 | −1,12 | +0,30 | 34 % | 0,20 | −1,56 |
| alternativ: Mindestlasten 30/50/10 % und Anfahrkosten | 18,55 | −0,42 | +1,00 | 13 % | 0,59 | −0,47 |

Die LP-Fahrpläne erreichen ihren Vorteil mit 250–390 Starts von KWK und GT. Mit den angenommenen Anfahrkosten bewertet,
sind sie bei fester MVA sogar teurer als IST (+0,37 M€/a). Der UC-Fahrplan kommt mit 12 KWK- und 60 GT-Starts aus (IST:
70 und 121). Er hält die GT dafür oft auf Mindestlast (1 329 h bei 4,9 MW) – mit konstantem Wirkungsgrad, siehe Grenzen.

Hilfsvarianten (`meta.json`, nicht in der Treppe):

- Nur die 348 MVA-Ausfallstunden gesperrt, sonst Monats-P95: 16,00 M€/a.
- MVA ≤ gemessen, aber frei nach unten: 17,44 M€/a. Das sind 0,10 M€/a weniger als „fest“, weil die MVA zu Hochpreiszeiten der KWK weichen könnte.
- KWK-Grenze 4,0 bar ohne Reserve: 17,55 M€/a.

### Kennzahlen je Fahrplan (Auszug aus `kennzahlen.csv`)

| Kennzahl | IST | MILP_H | MVA_IST + KWK-Grenze | MILP_UC | UC 30/50/10 % | REGEL |
|---|---:|---:|---:|---:|---:|---:|
| Betriebskosten [M€/a] | 18,97 | 15,71 | 17,55 | 17,85 | 18,55 | 19,43 |
| Brennstoff / CO2 / Steuer [M€/a] | 27,13 / 6,27 / 0,21 | 26,04 / 5,84 / 0,06 | 28,09 / 6,56 / 0,09 | 28,14 / 6,58 / 0,12 | 27,66 / 6,43 / 0,24 | 24,90 / 5,60 / 0,00 |
| Stromerlös [M€/a] | −14,63 | −16,24 | −17,18 | −16,98 | −15,77 | −11,06 |
| Wärme KWK / MVA / GT / BIO / HW1 [GWh/a] | 161 / 238 / 71 / 126 / 36 | 146 / 270 / 80 / 126 / 10 | 165 / 238 / 88 / 126 / 15 | 157 / 238 / 91 / 126 / 20 | 143 / 238 / 85 / 126 / 40 | 268 / 238 / 0 / 126 / 0 |
| Betriebsstunden KWK / GT / HW1 [h] | 4 346 / 3 109 / 3 610 | 4 237 / 3 077 / 606 | 4 796 / 3 496 / 939 | 4 133 / 4 552 / 2 216 | 2 680 / 3 090 / 3 764 | 6 557 / 1 / 0 |
| Vollbenutzungsstunden KWK / GT / HW1 [h] | 1 268 / 2 025 / 893 | 1 147 / 2 273 / 262 | 1 299 / 2 522 / 372 | 1 235 / 2 611 / 496 | 1 128 / 2 435 / 999 | 2 111 / 0 / 0 |
| Strom KWK / GT [GWh/a] | 38,4 / 54,8 | 34,7 / 61,4 | 39,3 / 68,2 | 37,4 / 70,6 | 34,1 / 65,8 | 63,9 / 0,0 |
| Erzielter Preis KWK / GT [€/MWh] | 107,5 / 116,6 | 109,8 / 135,4 | 105,9 / 130,7 | 106,8 / 125,8 | 111,0 / 119,6 | 108,8 / – |
| KWK-Strom bei negativem Preis [GWh/a] (h) | 0,82 (140) | 0,15 (32) | 0,27 (83) | 0,39 (103) | 0,21 (20) | 1,27 (312) |
| GT-Strom bei negativem Preis [GWh/a] (h) | 0,14 (31) | 0 (0) | 0 (0) | 0,10 (25) | 0,93 (68) | 0 (0) |
| CO2 aus Brennstoff [kt/a] | 87,0 | 81,2 | 91,1 | 91,3 | 89,3 | 77,7 |
| Anfahrten KWK / GT / HW1 | 70 / 121 / 250 | 251 / 369 / 114 | 325 / 392 / 164 | 12 / 60 / 224 | 61 / 126 / 273 | 120 / 1 / 0 |
| Rampen Σ\|ΔQ\| KWK / GT / HW1 [GWh/a] | 13,3 / 8,0 / 8,7 | 30,1 / 18,7 / 4,3 | 33,8 / 19,3 / 5,5 | 23,0 / 14,3 / 7,1 | 15,7 / 11,7 / 13,4 | 22,2 / 0 / 0 |
| h unter Mindestlast P5 IST, KWK / GT / HW1 | 216 / 158 / 176 | 825 / 164 / 45 | 1 045 / 314 / 154 | 0 / 0 / 521¹ | 0 / 0 / 521¹ | 1 548 / 1 / 0 |
| h unter 30/50/10 %, KWK / GT / HW1 | 2 004 / 1 200 / 541 | 2 505 / 800 / 86 | 2 817 / 992 / 206 | 2 254 / 2 138 / 914¹ | 0 / 0 / 687¹ | 3 409 / 1 / 0 |
| KWK-Δp Modell Mittel / P95 / Max [bar] | 1,64 / 2,28 / 3,64 | 1,65 / 2,54 / 6,00 | 1,68 / 2,64 / 3,36 | 1,66 / 2,57 / 3,36 | 1,66 / 2,64 / 3,36 | 1,90 / 3,22 / 7,14 |
| h KWK-Δp > 4,0 bar / > 3,36 bar | 0 / 3 | 30 / 76 | 0 / 0 | 0 / 0 | 0 / 0 | 111 / 312 |
| h mit Grenzverletzung (Studiengrenzen) | 0 | 0 | 0 | 0 | 0 | 0 |
| Pumpenstrom (nicht in den Kosten) [MWh/a] | 2 098 | 2 541 | 2 364 | 2 333 | 2 301 | 1 919 |

¹ HW1 darf im Stundenmittel unter die Mindestlast, wenn die Restlast nach MVA und BIO selbst kleiner ist (Takten
innerhalb der Stunde, siehe Annahmen); 2 723 bzw. 2 889 h, fast nur Mai–September.

Notkühlung: MILP_UC 0,07 MWh in 1 h. MILP_UC_PROZENT 348 MWh in 48 h (Feb./März/Okt.); dort zwingt die KWK-Mindestlast
von 38,1 MW bei fester MVA Wärme in die Notkühlung. Die 30-%-Annahme widerspricht dem gemessenen Betrieb: IST fährt die
KWK in 2 004 h unter 38,1 MW. Für den Vergleich ist daher MILP_UC (P5 IST) maßgeblich.

**Hydraulik.** Der Modell-Mindestbedarf der KWK-Δp für den IST-Fahrplan liegt im Mittel 0,64 bar unter der Messung
(RMSE 0,74 bar, r = 0,77). Gemessen: Mittel 2,29 bar, P95 3,25 bar, Max. 4,16 bar, 5 h über 4,0 bar. Diese mittlere
Differenz ist die Betriebsreserve, die von 4,0 bar abgezogen wird. Das Studien-MILP verletzt die Studiengrenzen nicht
(Mode H), fährt die KWK aber in 30 h über 4,0 bar (Modell). Das reale Netz hätte das nach dem Erfahrungswert nicht
erlaubt. Die Grenze kostet bei fester MVA nur 5 k€/a.

### Wasserfall IST → MILP (`wasserfall.csv`, M€/a)

| Kategorie | → MILP_H (Studie) | → MVA_IST + KWK-Grenze | → MILP_UC | → UC 30/50/10 % | → REGEL |
|---|---:|---:|---:|---:|---:|
| a) HW1 statt KWK (Menge) | −0,36 | −0,30 | −0,23 | +0,06 | −0,51 |
| b) GT statt KWK (Menge) | −0,13 | −0,25 | −0,30 | −0,21 | +1,03 |
| b) Strompreis-Verlagerung GT (Zeitpunkt) | −1,16 | −0,96 | −0,65 | −0,20 | 0,00 |
| b) Strompreis-Verlagerung KWK (Zeitpunkt) | −0,08 | +0,07 | +0,03 | −0,12 | −0,08 |
| c) MVA/BIO-Auslastung (Menge + Zeitpunkt) | −1,53 | +0,04 | +0,04 | +0,04 | +0,04 |
| d) Rest (HW1-Zeitpunkt, Bilanzabweichung) | −0,02 | −0,02 | −0,02 | +0,01 | −0,02 |
| **Summe** | **−3,27** | **−1,42** | **−1,12** | **−0,42** | **+0,46** |

Die +0,04 M€/a in c) bei fester MVA entstehen bei der BIO. Das Modell begrenzt sie auf m_max · Δh, gemessen lag sie in
5 430 h darüber (126,2 statt 126,0 GWh/a).

Einordnung über die Grenzkosten bei 2025-Preisen (Wärme, €/MWh_th):

| Anlage | Grenzkosten |
|---|---|
| KWK | 84,1 − 0,238 λ |
| GT | 134,1 − 0,773 λ |
| HW1 | 72,6 (fest) |

Daraus folgen drei Preisschwellen:

- **λ > 93,5 €/MWh** (4 262 h): GT ist billiger als KWK.
- **λ < 48,1 €/MWh** (1 486 h): HW1 ist billiger als KWK.
- **λ > 79,5 €/MWh** (5 993 h): GT ist billiger als HW1.

IST erzeugte 31,2 der 35,7 GWh HW1-Wärme bei λ > 48,1 €/MWh, also in Stunden, in denen die KWK billiger gewesen wäre
(MILP_UC: 8,3 von 19,9 GWh). Ein Teil davon dürfte Gründe haben, die das Modell nicht kennt: Reserve,
Verfügbarkeit, Hydraulik, Personal.

### Differenz je Monat und je Preisklasse (`differenz_monat.csv`, `differenz_preisklasse.csv`, k€)

| Monat | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IST → MILP_H | −288 | −473 | −511 | −199 | −183 | −15 | −30 | −44 | −463 | −462 | −254 | −347 |
| IST → MVA_IST + KWK-Grenze | −181 | −389 | −276 | −148 | −46 | +21 | +14 | −2 | −105 | −140 | −76 | −93 |
| IST → MILP_UC | −176 | −380 | −223 | −104 | −19 | +30 | +25 | +11 | −71 | −78 | −55 | −80 |

Auf September (MVA-Revision) und Oktober entfallen 0,93 der 3,27 M€/a Studienvorteil. Davon gehen ≈ 0,68 M€/a auf die
MVA zurück: Mit fester MVA bleiben in diesen Monaten nur 0,25 M€/a. Mit fester MVA liegt der Vorteil vor allem im Winter.

Im Sommer ist das MILP teurer als IST (MILP_UC +11 bis +30 k€/Monat). Grund: BIO und MVA liefern im Modell etwas weniger,
die BIO wegen des Deckels m_max · Δh, die MVA nur bis zur Last. Die kleinen Restlasten deckt dann HW1 (+1,9 GWh, +0,14 M€
in Juni–August). Im IST schließt die KWK sie mit sehr kleinen Werten (Messwerte < 1 MW).

| Preisklasse [€/MWh] | Stunden | IST → MILP_H | IST → MVA_IST + KWK-Grenze | IST → MILP_UC | IST → REGEL |
|---|---:|---:|---:|---:|---:|
| < 0 | 576 | −198 | −38 | −24 | +18 |
| 0–50 | 942 | −368 | −135 | −87 | −59 |
| 50–100 | 3 731 | −1 110 | −233 | −139 | −212 |
| 100–150 | 2 873 | −1 047 | −612 | −509 | +227 |
| > 150 | 637 | −545 | −403 | −361 | +485 |

### Regel-Vergleiche

- **REGEL vs. IST: +0,46 M€/a.** Die Regel fährt die KWK vor der GT (268 statt 161 GWh KWK, keine GT) und verliert
  damit vor allem in Stunden > 100 €/MWh (+0,71 M€/a). Sie spart dafür bei HW1 (−0,51 M€/a). Der heutige Betrieb ist also
  deutlich besser als eine starre wärmegeführte Merit-Order.
- **REGEL → MILP mit fester MVA: −1,89 M€/a**, davon −4,20 M€/a durch mehr GT statt KWK und +1,99 M€/a durch den
  Zeitpunkt der GT-Stunden. IST holt davon 0,46 M€/a (24 %); gegen MILP_UC (−1,58 M€/a) 29 %.
- Die Regel ist hydraulisch nicht eingeschränkt: Die KWK läge in 111 h über 4,0 bar (Modell, max. 7,1 bar).

### Darstellungswochen (`wochen.csv`, PNG)

Die Wochen laufen jeweils Montag bis Sonntag.

| Woche | Beginn | Auswahlkriterium |
|---|---|---|
| Kältewoche | 03.02.2025 | Woche mit der Höchstlast Januar/Februar |
| Übergangswoche | 21.04.2025 | größte Day-Ahead-Spreizung im April/Oktober |
| Sommerwoche | 09.06.2025 | mittlere Last am nächsten am Median der Sommerwochen |

Spalten: Last, Day-Ahead-Preis, Wärme je Anlage für IST, MILP_H und zusätzlich MILP_UC. Die Übergangswoche zeigt
die Hauptunterschiede: IST deckt die Restlast über MVA/BIO fast nur mit HW1, das MILP mit GT bei hohen und mit KWK/HW1
bei niedrigen Preisen.

## Annahmen

- **Kosten und Preise** wie in der Studie (`base.yaml`):
  - Gas 48 €/MWh, CO2 72 €/t, Biomasse 20 €/MWh, MVA-Übernahme 10 €/MWh_th, Energiesteuer HW1 5,5 €/MWh.
  - η wie in der Studie; KWK-Strom zum Day-Ahead-Preis DE-LU 2025 (Mittel 89,3 €/MWh, 576 negative Stunden).
  - Kein Netz-CO2-Faktor im Kostenansatz. Die lokale Datei des Netzfaktors liegt in dieser Umgebung nicht vor; die CO2-Kennzahl ist Brennstoff-CO2.
- **IST:**
  - Gemessene Wärme mit Interpolation von Lücken ≤ 6 h (KWK 102, MVA 39, GT 3 h).
  - HW1 fehlend = 0 (2 919 h), BIO fehlend = Median (483 h), MVA verbleibend fehlend = 0 (335 h, davon 334 in MVA-Ausfallstunden).
  - Die KWK schließt die Bilanz zur Last. Sie weicht in 326 h von der gemessenen KWK ab, Summe 2,07 GWh/a. In 70 h liegt die IST-Summe über der Last (max. 13,3 MW, 0,26 GWh/a), weil die KWK nicht negativ werden kann.
  - In 335 h ist die Last modelliert ergänzt.
  - Grenzverletzungen des IST gegen die Modellgrenzen werden gezählt, nicht gekappt (`ist_grenzpruefung.csv`): GT 172 h über der Obergrenze (max. 8,7 MW), MVA 427 h über Monats-P95, BIO 5 430 h über m_max · Δh (max. 4,6 MW), Ost-Parallelgrenze 99 h.
- **MVA fest wie gemessen:** Obergrenze = gemessene Wärme der Stunde, Untergrenze ebenso. Sie gilt nur, solange die Last nach BIO größer ist; die gemessene MVA darf dabei über der Modellkapazität liegen. MVA-Ausfall = < 1 MW oder Messlücke bei Vorlauf ≤ 90 °C (348 h).
- **KWK-Grenze:**
  - Erfahrungswert 4,0 bar am Standort der KWK, abzüglich der mittleren Differenz Messung − Modell im IST (0,64 bar), also 3,36 bar auf den Modell-Mindestbedarf.
  - Harte Grenze über `hydraulics.kwk_experience_value_hard` mit Schnitten wie in Mode H.
- **Mindestlasten:**
  - P5 der IST-Last in Betriebsstunden (KWK 11,8, GT 4,9, HW1 2,4 MW); KWK und GT sind aggregierte Mehrblockanlagen.
  - Alternative laut Aufgabe 30/50/10 % der Kapazität.
- **Anfahrkosten:** 5 / 2 / 0,2 k€ je Start (KWK / GT / HW1). Anfangszustand = IST-Zustand der ersten Stunde.
- **Takten HW1:** Ein Kessel kann innerhalb der Stunde takten. HW1 darf daher im Stundenmittel unter die Mindestlast, wenn die Restlast nach den Muss-Anlagen (MVA, BIO) kleiner als die Mindestlast ist. Ohne diese Regel erzwang der Sommer 3,75 GWh Notkühlung, weil HW1 Restlasten von 0,1–2,4 MW nur mit 2,4 MW decken konnte – ein Artefakt der festen MVA und BIO.
- **Notkühlung im UC:** 10 000 €/MWh Strafe, nur wenn sonst unzulässig. Die Strafe zählt nicht zu den Kosten, der Brennstoff der weggekühlten Wärme schon.

## Grenzen

- **Perfekte Voraussicht** für Last und Day-Ahead-Preise. Der Betrieb kennt beide nur als Prognose; die Studie zeigt im
  rollierenden Horizont, dass ein Teil des Optimierungsvorteils dadurch verloren geht. Der Vergleich ist eine obere Schranke.
- **Nur Day-Ahead:** Intraday-Handel, Regelenergie (Vorhaltung und Abruf) und Bilanzkreisführung fehlen. Der reale Einsatz
  kann Erlöse aus diesen Märkten enthalten, die hier fehlen – IST erscheint dann zu teuer, der Vorteil zu groß.
- **Verträge und Fahrplanbindungen** (Gaslieferung, Strombezug und -vermarktung, MVA-Abnahmevertrag) sind nicht abgebildet.
- **Revisionen und Verfügbarkeit:** Nur die MVA-Ausfälle sind aus der Messung bekannt. Revisionen, Störungen und
  Reservehaltung von KWK, GT und HW1 fehlen; HW1-Einsatz zur Absicherung (n−1) erscheint im MILP als vermeidbar.
- **Teillastwirkungsgrade** sind konstant. Die UC-Lösung hält die GT oft auf 4,9 MW; bei realem Teillast-η wäre das
  teurer. Mindestbetriebs- und Mindeststillstandszeiten fehlen.
- **Netzverluste und Last** sind für alle Fahrpläne gleich; temperaturabhängige Verluste und Rücklaufeinflüsse eines
  anderen Einsatzes sind nicht rückgekoppelt.
- **Hydraulik:** Ersatznetz mit Kalibrierung A, Mindestbedarf statt gefahrener Δp. Die Betriebsreserve ist ein Mittelwert,
  die Streuung (RMSE 0,74 bar) bleibt.
- **Pumpenstrom** ist nicht in den Kosten (wie im MILP). Er unterscheidet sich zwischen den Fahrplänen um bis zu 0,6 GWh/a,
  bei 100 €/MWh also ≲ 0,06 M€/a.
- **Gemessene Stromwerte** liegen nicht vor; KWK-Strom = Wärme · η_el/η_th. Der Stromerlös des IST ist daher modelliert,
  ebenso der Wärmeanteil der Brennstoffkosten.
- **Personal, Fahrweise in Schichten, Netzführung** (Druckhaltung, Temperaturvorgaben über das Δp-Kriterium hinaus) sind
  nicht abgebildet.
- **Day-Ahead-Preise:**
  - Die Datei `data/prices/raw_2025.json` (energy-charts.info, Quelle BNetzA | SMARD.de, CC BY 4.0) liegt nicht im Repository.
  - Sie wurde für diesen Lauf monatsweise über die API abgerufen.
  - Wer das Skript ausführt, braucht sie unter `data/prices/` (gleiches Format wie die übrigen `raw_<Jahr>.json`).

## Dateien

In `results/central_tes/dispatch_comparison/`:

| Datei | Inhalt |
|---|---|
| `kennzahlen.csv` | alle Kennzahlen je Fahrplan |
| `fairness.csv` | Fairness-Treppe |
| `wasserfall.csv` | Zerlegung je Vergleich |
| `differenz_monat.csv` | Differenz je Monat [k€] |
| `differenz_preisklasse.csv` | Differenz je Preisklasse [k€] |
| `wochen.csv` | Darstellungswochen |
| `dauerlinien.csv` | Jahresdauerlinien je Fahrplan und Anlage |
| `dp_kwk.csv` | KWK-Δp: gemessen, IST modelliert, je Fahrplan |
| `ist_grenzpruefung.csv` | Grenzverletzungen des IST |
| `meta.json` | Bilanzprüfung, Solver, Hilfsvarianten, UC-Details |
| `uc_info.json` | UC-Lösungsdetails |
| `fahrplan_*.parquet` | Fahrpläne |
| `png/` | Wochen gestapelt mit Preislinie, Wasserfall, Wärme je Anlage, Dauerlinien HW1/KWK |

Alle CSV-Dateien: UTF-8, Komma als Trenner, Punkt als Dezimalzeichen.
