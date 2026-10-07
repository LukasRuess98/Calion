# Autoren-Referenz — agnes_p2h

Automatisch erzeugt aus `outputs/20260922T203807/`. Diese Datei sammelt alles, was gebraucht wird, um den Paper-Draft manuell (oder per Skript, s. bereits erzeugtes `draft_filled.md` im selben Ordner) mit Abbildungen, Tabellen und Ergebnissen zu befüllen.

**Belegte Marker:** 48  **Offene Marker:** 5  **Quellordner:** `outputs/20260922T203807/`

## 1. Abbildungen

### Abb. 1 — `fig01_superstructure`

- **Datei:** `figures/fig01_superstructure.pdf` / `figures/fig01_superstructure.png`
- **Bildunterschrift-Vorschlag:** Systemgrenze / Superstruktur: Grundlast + Wärmepumpe + Elektrodenkessel + Gaskessel speisen (über Wärmespeicher) ein Prozesswärme-Band; Netzentgelt gilt für den GESAMTNETZBEZUG (G-04). Statische Abbildung, kein Datenbezug.

### Abb. 2 — `fig02_analytics`

- **Datei:** `figures/fig02_analytics.pdf` / `figures/fig02_analytics.png`
- **Quelldaten:** `fig02_analytics_sigma.csv`, `fig02_analytics_theta.csv`
- **Bildunterschrift-Vorschlag:** (a) sigma_NEV(h) vs. sigma_AgNes(h) für Ebene MS, log-x, mit h*-Marker: zeigt den nach oben unbeschränkten Aufschlag unter StromNEV gegenüber dem auf AP2-AP1 gedeckelten Aufschlag unter AgNes. (b) theta(alpha,f)-Heatmap mit der Isolinie theta=1 -- zeigt die in R-01 belegte Spannweite (Faktor 8,75).

### Abb. 3 — `fig03_core_results`

- **Datei:** `figures/fig03_core_results.pdf` / `figures/fig03_core_results.png`
- **Quelldaten:** `fig03a_lcoh.csv`, `fig03_core_results.csv`
- **Bildunterschrift-Vorschlag:** (a) Inkrementelle Wärmekosten (LCOH^inc) je Standort über die vier Regime 00/01/10/11. (b) Anlagenauslegung (HP/EK/GB, gestapelt) unter AgNes/Day-Ahead. (c) Wärmespeicherkapazität je Standort (ein Band) unter AgNes/Day-Ahead.

### Abb. 4 — `fig04_load_duration`

- **Datei:** `figures/fig04_load_duration.pdf` / `figures/fig04_load_duration.png`
- **Quelldaten:** `fig04_load_duration.csv`
- **Bildunterschrift-Vorschlag:** Jahresdauerlinien je Standort (ELEC, AgNes, Day-Ahead) mit bestellter Kapazität C, realisiertem P_max, der E2-Fläche (Bezug oberhalb C) und h*-Marker auf der Dauerachse -- zentrale Abbildung für den Bestellregel-Befund (§6.4).

### Abb. 5 — `fig05_breakeven`

- **Datei:** `figures/fig05_breakeven.pdf` / `figures/fig05_breakeven.png`
- **Quelldaten:** `breakeven.csv`, `breakeven_shift.csv`
- **Bildunterschrift-Vorschlag:** Fossiler Break-even-Gaspreis und -CO2-Preis je Standort UND Netzregime (ELEC vs. GAS, Day-Ahead-Beschaffung, ELEC-Kapazitäten aus dem jeweiligen S1-Optimum im Redispatch-Modus).

## 2. Tabellen

### Tab. 1 — Modellrelevanter Regimevergleich StromNEV vs. AgNes mit Fundstellen.

| Element                                           | StromNEV                                | AgNes                                                                                                                                                         | Fundstelle                                                                              | Freigabestatus      |
|:--------------------------------------------------|:----------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------|:--------------------|
| Bemessungsgröße Leistungsentgelt                  | Gemessene Jahreshöchstlast $P^{max}$    | Frei bestellte Kapazität $C$                                                                                                                                  | StromNEV §19 Abs.2 / GBK-25-01-1#3                                                      | reviewed            |
| Arbeitspreisstruktur                              | Ein Arbeitspreis je Tarifpaar           | Zweistufig: $AP_1$ (<=C), $AP_2$>$AP_1$ (>C)                                                                                                                  | GBK-25-01-1#3                                                                           | reviewed            |
| Schwellenwert / Bestellgrenzen                    | 2500 h/a (zwei Tarifpaare)              | beta=0.1 x P^max,prev <= C <= P^grid                                                                                                                          | StromNEV § 19 Abs. 2 (Struktur, Schwelle 2.500 Benutzungsstunden/Jahr)                  | reviewed/unverified |
| Bestellzeitpunkt                                  | n/a (ex-post gemessen)                  | Vor Jahresbeginn (ex ante)                                                                                                                                    | GBK-25-01-1#3                                                                           | reviewed            |
| Maximaler Leistungsaufschlag bei geringer Nutzung | Unbeschränkt für h->0 (sigma=1000 LP/h) | Beschränkt auf AP2-AP1 (Ebene ms: 69.3 EUR/MWh)                                                                                                               | §3.4 Draft (abgeleitet)                                                                 | derived             |
| Status Regelwerk                                  | Geltendes Recht                         | Festlegungsentwurf (2026-08-06), Konsultation bis 2026-09-18, geplant ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils) | https://www.bundesnetzagentur.de/DE/Beschlusskammern/GBK/Ebene1_Rahmen/AgNes/start.html | reviewed            |

Rohdaten: `tables/table01_regulatory.csv`

### Tab. 2 — Standortübersicht (Wärmebedarf, Volllaststunden, Grundlast, Ebene, P_grid, P_max_prev).

| Standort                              |   Wärmebedarf [MWh_th/a] |   Wärme-Peak [MW_th] |   Wärme-Volllaststunden [h/a] |   Grundlast Ø [kW] |   Grundlast max [kW] | Spannungsebene   |   P_max,prev [kW] | hat VHT   |   Lastgangjahr |   Preisjahr |
|:--------------------------------------|-------------------------:|---------------------:|------------------------------:|-------------------:|---------------------:|:-----------------|------------------:|:----------|---------------:|------------:|
| Lebensmittelunternehmen (Schwarzwald) |                  75046.4 |                18.84 |                          3983 |             5800.2 |              16452.8 | ms               |           16452.8 | False     |           2023 |        2023 |
| Chemieunternehmen (Essen)             |                  53474.3 |                13.81 |                          3871 |             4640.4 |               6449.3 | ms               |            6449.3 | False     |           2024 |        2024 |
| Metallerzeugung (Schwarzwald)         |                    254.5 |                 0.14 |                          1885 |              109.6 |                722.9 | ns               |             722.9 | False     |           2023 |        2023 |
| Papierfabrik (Augsburg)               |                 232767   |                59.9  |                          3886 |            30725.6 |              54927.4 | hs_ms            |           54927.4 | False     |           2023 |        2023 |

Rohdaten: `tables/table02_cases.csv`

### Tab. 3 — Kern-KPI je Standort (LCOH_inc, Delta_Netz, Delta_Preis, Delta_inter, C/P_max, E2/E).

| Standort                |   LCOH_inc_00_StromNEV_Fix |   Delta_Netz_Fix_AgNes-StromNEV |   Delta_Netz_DA_AgNes-StromNEV |   Delta_Preis_StromNEV_DA-Fix |   Delta_Preis_AgNes_DA-Fix |   Delta_inter |   C_over_Pmax_AgNes_DA |   E2_over_E_AgNes_DA |
|:------------------------|---------------------------:|--------------------------------:|-------------------------------:|------------------------------:|---------------------------:|--------------:|-----------------------:|---------------------:|
| Lebensmittelunternehmen |                      35.45 |                           14.92 |                          15.08 |                         -4.77 |                      -4.61 |          0.16 |                   0.79 |                 0.01 |
| Chemieunternehmen       |                      53.29 |                            3.77 |                           8.53 |                         -4.77 |                      -0.01 |          4.76 |                   0.78 |                 0.01 |
| Metallerzeugung         |                      58.51 |                           -4.08 |                          -8.46 |                          0.00 |                      -4.38 |         -4.38 |                   0.15 |                 0.55 |
| Papierfabrik            |                      45.10 |                            4.92 |                           4.87 |                         -4.87 |                      -4.92 |         -0.05 |                   0.91 |                 0.01 |

Rohdaten: `tables/table03_core_results.csv`

### Supplement (vollständige Sweep-/Testergebnisse)

- `tables/supplement_s10_rolling_horizon.csv`
- `tables/supplement_s5_alpha_f.csv`
- `tables/supplement_s7_breakeven.csv`
- `tables/supplement_s8_decomposition.csv`
- `tables/supplement_s9_demand.csv`
- `tables/supplement_test_report.csv`

## 3. Kernzahlen nach Draft-Abschnitt

Jede Zeile: Marker im Draft (`[[MARKER]]`) -> Wert -> woher (KPI/Datei).

### Titel/Fußnote 1

| Marker | Wert | Quelle |
|---|---|---|
| `REG-01` | Az. GBK-25-01-1#3, Entwurf 2026-08-06, Konsultation bis 2026-09-18, Anwendung ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils) | `config.yaml` |

### Abstract DE/EN

| Marker | Wert | Quelle |
|---|---|---|
| `R-ABS-01` | LCOH^inc zwischen 30,7 und 58,5 EUR/MWh_th (4 Standorte x 4 Regime) | `lcoh_inc.csv` |
| `R-ABS-02` | TES-Kapazität verschiebt sich um von -14.671 bis 1.380 kWh zwischen StromNEV- und AgNes-Fixpreis-Auslegung | `design_deltas.csv` |
| `R-ABS-03` | 34,7 % | `rule_validation.csv` |

### Kernaussagen (ZWF-Kasten)

| Marker | Wert | Quelle |
|---|---|---|
| `R-CORE-01` | food: 34,7%; chemistry: 0,9%; metal: 9,9%; paper: 27,0% | `rule_validation.csv` |
| `R-INT-01` | substitutiv (Interaktionsterm überwiegend negativ) | `interaction.csv` |

### §2 AgNes vs. StromNEV / Tab.1

| Marker | Wert | Quelle |
|---|---|---|
| `REG-02` | **OFFEN** — Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung (z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) ist real und wird als Limitation benannt, nicht geglättet. | — |
| `REG-03` | **OFFEN** — Nachrecherchiert, weiterhin offen: Der veröffentlichte AgNes-Entwurf und Presseberichte zum Konsultationsstand (2026-08-06 bis 2026-09-18) klären nicht abschließend, ob elektrische Wärmeerzeuger regulär oder in einem Sonderregime behandelt werden. Ein indirekter, für die Diskussion relevanter Befund: saisonal differenzierte Arbeitspreise wurden von der BNetzA explizit VERWORFEN, weil sie den Betrieb von Wärmepumpen deutlich verteuern würden - ein Hinweis, dass keine gezielte Verteuerung elektrischer Wärmeerzeuger beabsichtigt ist, aber keine formale Entscheidung zum Letztverbraucher-Regime. Nicht aus Daten ableitbar. | — |
| `REG-04` | **OFFEN** — Offen: Übergangsregelungen/Flexibilitäts-Sondernetzentgelt sind nicht Teil des Kernmodells (Draft §2.5) und daher nicht quantifizierbar. Recherche zum Konsultationsstand liefert keine über REG-01 hinausgehenden Details zu Übergangsfristen. | — |

### §3.3 Dimensionslose Form theta

| Marker | Wert | Quelle |
|---|---|---|
| `R-01` | Faktor 8,75 | `fig02_analytics_theta.csv` |

### §6.1 Datenqualität und Validierung

| Marker | Wert | Quelle |
|---|---|---|
| `R-VAL-01` | food: 35040, chemistry: 35136, metal: 35040, paper: 35040 | `data_audit.md` |
| `R-VAL-02` | 1.1e-16 | `test_report.md` |
| `R-VAL-03` | 0.0e+00 | `kpi_s1_s4.parquet` |
| `R-VAL-04` | 96/96 optimal | `kpi_s1_s4.parquet` |
| `R-TIME-01` | chemistry: 6.440->6.449 kW; paper: 68.005->68.505 kW | `kpi_validation_15min.parquet` |
| `R-TIME-02` | chemistry: 0,04%; paper: 0,11% | `kpi_validation_15min.parquet` |

### §6.2 Kostenwirkung und Interaktion

| Marker | Wert | Quelle |
|---|---|---|
| `R-NET-FIX-MIN` | -4,1 | `table03_core_results.csv` |
| `R-NET-FIX-MAX` | 14,9 | `table03_core_results.csv` |
| `R-NET-DA-MIN` | -8,5 | `table03_core_results.csv` |
| `R-NET-DA-MAX` | 15,1 | `table03_core_results.csv` |
| `R-INT-NEG-N` | 2 von 4 | `interaction.csv` |
| `R-INT-MIN` | -4,4 | `interaction.csv` |
| `R-INT-MAX` | 4,8 | `interaction.csv` |
| `R-DEC-MECH` | 74,8 | `decomposition.csv` |
| `R-DEC-DISP` | 30,3 | `decomposition.csv` |
| `R-DEC-DESIGN` | -5,1 | `decomposition.csv` |

### §6.3 Auslegung

| Marker | Wert | Quelle |
|---|---|---|
| `R-DES-HP` | von -4.850 bis 38 kW über 4 Standorte | `design_deltas.csv` |
| `R-DES-EK` | von 0 bis 0 kW über 4 Standorte | `design_deltas.csv` |
| `R-DES-EF` | **OFFEN** — n/a: VHT/E-Ofen ist gemäß Teil-3-Entscheidung #2 als Limitation behandelt (Rohdaten stützen keine VHT-Bandtrennung), daher kein EF in diesem Modell. | — |
| `R-TES-MIN` | -14.671 | `design_deltas.csv` |
| `R-TES-MAX` | 1.380 | `design_deltas.csv` |
| `R-TES-VALUE` | 361.848 EUR/a Summe über alle S1-Zellen | `kpi_s1_s4.parquet` |
| `R-TES-CASE` | (a) h>h*: 3 Standorte, (b) h<h*: 1 Standorte | `tes_case_check.csv` |

### §6.4 Bestellkapazität und Regelgüte

| Marker | Wert | Quelle |
|---|---|---|
| `R-BOOK-MIN` | 15 % | `lcoh_inc.csv` |
| `R-BOOK-MAX` | 91 % | `lcoh_inc.csv` |
| `R-E2` | 14 % (Mittel) | `lcoh_inc.csv` |
| `V-01` | bestanden (T08, Abweichung < 0,5% im evaluate-Fall) | `test_report.md` |
| `V-04` | food: 0,00%; chemistry: 0,00%; metal: 0,00%; paper: 0,00% | `rule_kkt_consistency_check.csv` |
| `R-RULE-DEV` | 34,7 | `rule_validation.csv` |
| `R-RULE-DIR` | höher | `rule_validation.csv` |

### §6.5 Fossiler Break-even

| Marker | Wert | Quelle |
|---|---|---|
| `R-BE-GAS` | von 13 bis 32 (über beide Netzregime, 7/8 Ketten konvergiert) | `breakeven.csv` |
| `R-BE-CO2` | von 11 bis 30 (über beide Netzregime, 2/8 Ketten konvergiert) | `breakeven.csv` |
| `R-BE-SHIFT` | food/gas: 104,9%; chemistry/gas: 18,9%; paper/gas: 21,2% | `breakeven_shift.csv` |

### §6.6 Tarifsensitivität / Tab.3

| Marker | Wert | Quelle |
|---|---|---|
| `R-SENS-C` | 63.456 | `kpi_s5_alpha_f.parquet` |
| `R-SENS-TES` | 37.895 | `kpi_s5_alpha_f.parquet` |
| `R-SENS-THETA` | bei theta>1 erreicht C in 0% der Läufe >=98% von P_max (vs. 2% bei theta<=1) | `kpi_s5_alpha_f.parquet` |
| `V-02` | Technologie-Rangfolge (größter Erzeuger) stabil unter Wärmelast +-10% bei 4/4 Standorten | `kpi_s9_demand_sensitivity.parquet` |

### §7.4 Grenzen (Perfect Foresight vs. Rolling Horizon)

| Marker | Wert | Quelle |
|---|---|---|
| `V-03` | stromnev/fixed: 0,09%; stromnev/dayahead: 0,10%; agnes/fixed: -0,00%; agnes/dayahead: -0,01% | `rolling_horizon.csv` |

### §8 Fazit

| Marker | Wert | Quelle |
|---|---|---|
| `R-CONCLUSION-01` | AgNes verschiebt die inkrementellen Wärmekosten je nach Standort und Beschaffungsregime um -4,1 bis 14,9 EUR/MWh (Fixpreis) bzw. -8,5 bis 15,1 EUR/MWh (Day-Ahead) ggü. StromNEV. | `table03_core_results.csv` |
| `R-CONCLUSION-02` | Die auf dem vor Elektrifizierung beobachteten Grundlastgang basierende Ex-ante-Bestellregel weicht im vollständig gekoppelten Elektrifizierungsmodell um bis zu 34,7% von der optimalen Bestellkapazität ab. Die Differenz umfasst die Wirkung des veränderten Gesamtlastgangs sowie Rückkopplungen aus Auslegung, Speicherbetrieb und Bestellentscheidung. Bei reinem Grundlastgang (V-01) bzw. bei Anwendung auf den vom LP realisierten Gesamtlastgang (V-04) trifft die Regel das Optimum exakt - die Abweichung ist damit korrekt der Elektrifizierung selbst zuzuschreiben, nicht einem Fehler der Regel. | `rule_validation.csv` |

### Literatur

| Marker | Wert | Quelle |
|---|---|---|
| `BIB-01` | Zühlsdorf, B., Armato, V., Poulsen, J. L., Andersen, M. P., Arpagaus, C., Schlosser, F., Dusek, S. (2024). IEA HPT Annex 58 High-Temperature Heat Pumps Final Report. DOI: 10.23697/2qxe-av87. | `config.yaml` |
| `BIB-02` | **OFFEN** — Offen: BNetzA-Monitoringbericht (Netzentgeltniveaus je Ebene) - s. REG-02. | — |
| `BIB-03` | Danish Energy Agency, Technology Data for Industrial Process Heat, 2023 (ens.dk Technology Catalogues, Sektor 'Industrial process heat'). | `config.yaml` |

## 4. Noch offene Punkte (manuell zu klären)

- **`REG-02`**: Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung (z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) ist real und wird als Limitation benannt, nicht geglättet.
- **`REG-03`**: Nachrecherchiert, weiterhin offen: Der veröffentlichte AgNes-Entwurf und Presseberichte zum Konsultationsstand (2026-08-06 bis 2026-09-18) klären nicht abschließend, ob elektrische Wärmeerzeuger regulär oder in einem Sonderregime behandelt werden. Ein indirekter, für die Diskussion relevanter Befund: saisonal differenzierte Arbeitspreise wurden von der BNetzA explizit VERWORFEN, weil sie den Betrieb von Wärmepumpen deutlich verteuern würden - ein Hinweis, dass keine gezielte Verteuerung elektrischer Wärmeerzeuger beabsichtigt ist, aber keine formale Entscheidung zum Letztverbraucher-Regime. Nicht aus Daten ableitbar.
- **`REG-04`**: Offen: Übergangsregelungen/Flexibilitäts-Sondernetzentgelt sind nicht Teil des Kernmodells (Draft §2.5) und daher nicht quantifizierbar. Recherche zum Konsultationsstand liefert keine über REG-01 hinausgehenden Details zu Übergangsfristen.
- **`R-DES-EF`**: n/a: VHT/E-Ofen ist gemäß Teil-3-Entscheidung #2 als Limitation behandelt (Rohdaten stützen keine VHT-Bandtrennung), daher kein EF in diesem Modell.
- **`BIB-02`**: Offen: BNetzA-Monitoringbericht (Netzentgeltniveaus je Ebene) - s. REG-02.

## 5. Weitere Dateien im Run-Ordner

- `draft_filled.md` — der komplette Draft mit automatisch eingesetzten Werten (Ausgangspunkt für die manuelle Überarbeitung)
- `open_issues.md` — methodische Abweichungen, unverified-Parameter-Liste
- `qa_report.md` — Selbsttest- und Solver-Diagnostik-Zusammenfassung
- `environment.md` — Run-ID, Config-Hash, Softwareversionen (für Reproduzierbarkeit)
