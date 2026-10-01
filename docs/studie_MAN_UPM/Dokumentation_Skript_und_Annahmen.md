# Dokumentation: Notebook `studie_grosswaermespeicher_MAN_UPM.ipynb` – Aufbau, Modelle, Annahmen, Prüfhinweise

Stand: 2026-10-01 · Gegenstand: hydraulisch-thermische Studie zur Wirkung eines direkt eingebundenen Druckspeichers (bis 120 °C) bei MAN/UPM im Fernwärmenetz Stadtbach (swa).
Zielgruppe: fachliche Prüfung (Hydraulik, Fernwärmebetrieb, Modellierung). **Dieses Dokument enthält abgeleitete Kennzahlen aus NDA-Daten (Abschnitt 7); vor externer Weitergabe freigeben.**

---

## 1. Überblick

| Punkt | Inhalt |
|---|---|
| Ergebnis des Auftrags | Ein einziges Notebook (24 Hauptkapitel), das Daten prüft, ein Netzmodell aufbaut, kalibriert/validiert, den Speicher in 45+ Szenarien bewertet, Maßnahmen vergleicht, mit pandapipes kontrolliert und Unsicherheiten quantifiziert |
| Quelle des Codes | **Nur das Notebook.** Es gibt keine neuen Projekt-Module. Das Notebook wurde aus Hilfsskripten generiert, die nicht versioniert sind; maßgeblich ist der Zelleninhalt. Eine Rückwärtsregenerierung ist nicht vorgesehen |
| Ausgaben | Im Repository liegt das Notebook **ohne Ausgaben** (NDA). Ergebnisdateien (CSV/PNG/MD) entstehen unter `results/studie_MAN_UPM/` (gitignoriert) |
| Daten | `data/Stadtbach/upload/…` (gitignoriert, NDA). Nicht im Repository |
| Begleitdokumente | `Datenanfrage_Betreiber.md` (offene Daten), diese Dokumentation |
| Sprache | Deutsch (Notebook, Ausgaben, Dokumentation) |

## 2. Reproduktion

1. Voraussetzungen (getestet): Python 3.11, numpy 2.4, pandas 2.3, scipy 1.16, matplotlib 3.11, pyomo 6.10 (Solver HiGHS 1.15 über `appsi_highs`, Paket `highspy`), pandapipes 0.14, pymupdf/rapidocr/scikit-image/opencv (nur für die Plan-Bildanalyse in Kap. 10.6), nbclient/ipykernel zum Ausführen. Paketversionen werden in Kap. 3 ausgegeben.
2. Daten nach `data/Stadtbach/upload/` legen (Struktur wie in Kap. 4 inventarisiert). Repo-Wurzel wird automatisch über den Ordner `calion/` gefunden (keine absoluten Pfade).
3. Notebook von oben nach unten ausführen. Rechenzeit: ca. 45–60 Minuten (davon Kalibrierung ca. 10–20 min, falls kein Zwischenspeicher `results/studie_MAN_UPM/kalibrierung.json` vorliegt; Hochlast-Test ca. 4 min; Sweeps/Unsicherheit ca. 15 min).
4. **Determinismus:** fester Seed `SEED = 20250101` für alle Zufallsziehungen (Kalibrierstichprobe, Monte-Carlo, Startwerte). Die Kalibrierung wird über eine Signatur (`sig_in`) gecacht; ändern sich Geometrie, Stichprobe oder Messunsicherheit, wird neu kalibriert.
5. **Vor jedem Commit Ausgaben entfernen** (NDA): `cell.outputs = []; cell.execution_count = None`.
6. Am Ende (Kap. 24) laufen **maschinelle Abnahmeprüfungen** (siehe Abschnitt 8); schlägt eine fehl, bricht das Notebook ab.

## 3. Datenquellen und Verwendung

| Quelle | Inhalt | Verwendung |
|---|---|---|
| `A_Daten/acron_stundenwerte_wert.parquet` (+ `acron_signalindex.csv`) | 169 Zeitreihen, stündlich 2025: Drücke (bar), Durchflüsse (m³/h), Temperaturen, Wärmeleistungen | Randbedingungen, Kalibrierung, Validierung, Bias-Korrektur |
| `A_Daten/Import_Data_stadtbach_15min.parquet` | Außentemperatur (15 min) | Heizkurve, Außentemperatur je Stunde |
| `A_Daten/acron_stundenwerte_minmax.parquet` | Stunden-Min/Max | nur Datenprüfung |
| `B_Plaene/640 Bl. 3 …pdf` | Erzeugerausspeisungen/-umwälzungen: Höhen (m NN), Ruhedruck HKW 8,4 bar Ü bei 474,68 m NN, Δp intern, PN-Zonen | Höhen der Erzeuger, Ruhedruck, Druckauslegung |
| `B_Plaene/WV650_Netz-Mitte_…pdf` | Sektionen SL1–SL7, Armaturen (≈ 124), Transportgrenzen Ost | Topologie, Trassenlängen (Bildanalyse), Schaltstellen |
| `B_Plaene/WV660_Netz-West_…pdf` | Westnetz SEK1–SEK3 (PN16, über Wärmeübertrager getrennt) | Westnetz als Entnahme |
| `configs/paper_2/Stadtbach_topo.yaml` | Topologie-Vorlage des Frameworks | Vergleich, Speicherprojektwerte (5 000 m³, 10 bar), Bodentemperatur 10 °C |
| `calion/models/network_physics.py` | Framework-Formeln | Gegenprüfung (Kap. 12.1) |
| `configs/pressure/Memmingen_pandapipes_crosscheck.ipynb` | alte pandapipes-Studie | nur Vorgehen (Kap. 20.1); Ergebnisse nicht übernommen |

## 4. Aufbau des Notebooks

| Kap. | Inhalt | Wichtige Funktionen/Objekte |
|---|---|---|
| 1–3 | Zusammenfassung (aus Ergebnissen erzeugt), Systemgrenze, Umgebung | `CFG`, `SEED`, `ROOT`, `RESULTS`, `FIG_DIR` |
| 4–5 | Dateiinventur; Annahmen-/Konfliktkatalog | `inspect`, `bewerte`; Tabellen `annahmenkatalog`, `konfliktkatalog` |
| 6–8 | Datenimport/-qualität, EDA, Heizkurvenprüfung | `kanal`, `longest_const_run`, `hk_vorgabe`, `hk_yaml` |
| 9–10 | Pläne, YAML-Topologie, Sektionsmodell v0.1 → v0.3 (Plangeometrie), Annahmenaudit | `farbmaske`, `trasse` (Bildanalyse), `set_edge`, `add_edge` |
| 11 | Gleichungen (Massen, Energie, Druckverlust, Pumpe, Mischung, Speicher, Kalibrierung) | – |
| 12 | Implementierung: Stoffwerte, Netzlöser, Randbedingungen, `simulate` | `rho_w`, `mu_w`, `psat_bar`, `cp_w`, `solve_network`, `simulate`, `station_pressures`, `rand_bed` |
| 13–14 | Kalibrierung (Jan–Sep 2025), Validierung (Okt–Dez 2025) | `residuals`, `objective`, `jac_fd`, `kenn` |
| 15 | Speicheranbindung (Varianten A/B), Szenario-Engine, Temperaturmodell | `solve_case`, `node_pressures`, `transport_T`, `thermal`, `conn_head_m`, `with_stor_node`, `with_theta` |
| 16 | Szenarien, Bias-Korrektur, Kennzahlen | `base_day_case`, `dispatch_rule`, `evaluate`, `compute_dp_bias`, `SCEN` |
| 17 | Optimierung der Speicherfahrweise | `probe`, `optimize_dispatch`, `storage_plan` |
| 18 | Ergebnisvergleich, Wirkungszerlegung, Druckauslegung, Abbildungen, historische Ereignisse | `decomp`, `CMP`, `RUN`, `KPI` |
| 19 | Ausbau, S9-Auslegungsvariation, Standortvariation, Druckanhebung, Ausbauverteilung, Hochlast-Kalibrierung, Maßnahmenvergleich | `s9_case`, `needed_raise`, `need`, `LOC`, `DR`, `DIST`, `MS` |
| 20 | pandapipes-Kontrollrechnung | `build_pp`, `run_pp`, `cmp_point`, `pp_chain` |
| 21 | Unsicherheit (Tornado, Monte-Carlo) | `eval_pair`, `TOR`, `MCD` |
| 22–24 | Schlussfolgerungen (20 Fragen + Zusatz), Empfehlung, Datenlücken, Plan, Export, Abnahmeprüfung | `ANS`, `reco`, `gaps`, `PLAN` |

Datenfluss: Messdaten → `BC` (Randbedingungen je Stunde) → `simulate`/`solve_case` (Vorlauf- und Rücklaufnetz getrennt) → `evaluate` (Kennzahlen) → `RUN` (alle Szenarien) → Vergleiche/Sweeps/Unsicherheit → Antworten/Export.

## 5. Modellbeschreibung (Kurzfassung; Gleichungen in Kap. 11)

**5.1 Netzmodell.** Sektionsmodell mit **25 Knoten und 30 Kanten** (7 unabhängige Maschen), Version v0.3. Knoten = Erzeuger, Pumpstationen, Kundenbereiche (Sektionen), Koppelstellen. **Vorlauf und Rücklauf werden getrennt gelöst** (je eigenes Druckhöhenfeld). Westnetz (PN16) ist nicht modelliert, nur als Entnahme `HWW` (Wärmeübertrager-Primärseite).

**5.2 Hydraulik.** Druckhöhenformulierung H = z + p/(ρ g); Kantengleichung ΔH = r·ṁ|ṁ| mit r = λ(Re) L /(D 2 g ρ² A²) · k_g; λ nach Swamee–Jain (turbulent), laminar 64/Re, Übergang 2300–4000 linear; Rauheit 0,1 mm. Knotenbilanz je Knoten; **Picard-Linearisierung** (Dämpfung 0,6, Mindestmassenstrom 0,05 kg/s, max. 300 Iterationen, Abbruch bei Δṁ < 1e-5 kg/s) mit mehreren Druckrandknoten (HKW und AVA/Ost-Sammler, gemessene Drücke). Pumpen (SL4c = PSS, W1 = PSW) als Druckhöhengewinn auf der Kante aus gemessenem Druckgewinn. Tests: Parallelrohre (analytisch), Ring (Schleifengesetz), Massen-/Kantenresiduum (Kap. 12.2); Szenario-Engine ≡ kalibrierte Simulation (Kap. 15.2).

**5.3 Stoffwerte.** Dichte Kell, Viskosität Vogel, Sättigungsdruck Wagner–Pruss (IAPWS), cp aus Tabelle; getestet gegen Referenzwerte (20/60/100/120 °C), Vergleich mit pandapipes-Wasser.

**5.4 Kalibrierung.** Parameter: Multiplikator k_g je **15 Leitungsgruppen** (13 frei; MAN-Anschluss und W1 fest 1,0), **9 Lastanteil-Logits** der Sektionen (Prior: Anschlussleistung), 6 Höhen-/Referenzoffsets (4 Ost-Stationen, 2 am Ost-Sammler VL/RL). Residuen: Druck an Messstellen (σ = 0,3 bar), Durchflüsse an HKW und AVA (σ = 25 m³/h), Ridge-Regularisierung. Verfahren `scipy.optimize.least_squares` (trf), Grenzen: k ∈ [0,2; 5] (Verbundkanten [0,02; 5]), Logit u ∈ [−0,9; 1,0] (Ost) bzw. [−1,6; 0,7], Offsets ±10 m (AVA-Referenz ±25 m). Stichprobe: 260 zufällige + 40 lastreichste Stunden (Jan–Sep). Beethovenpark (2,9 km DN150-Stichleitung) ist von der Kalibrierung ausgeschlossen.

**5.5 Temperaturmodell (Kap. 15.3).** Quasistationär, Aufwind-Mischung an Knoten, Rohrverlust T_aus = T_B + (T_ein − T_B)·exp(−U'L/(ṁ cp)) mit U' = 0,3 W/(m K), T_B = 10 °C. Nur Hauptleitungen; Verteilnetze fehlen (Verluste unterschätzt). Energiebilanz wird getestet.

**5.6 Speicher (Kap. 15).** Der Speicher ist im Netz eine **Massenstrom-Einspeisung/-Entnahme** am Knoten (Vorlauf +, Rücklauf −; Laden umgekehrt). Pumpenförderhöhe aus den Druckhöhen: H_P = (H_VL − H_RL)_Knoten + h_L,VL + h_L,RL. **Ohne Pumpe ist Entladen unmöglich** (p_VL > p_RL), Laden nur bis zum Netz-Δp (Variante A). Füllstand: E_{t+1} = E_t + η Q_c − Q_d/η − Q_Verlust (η = 0,98), nutzbare Kapazität E = ρ c_p V ΔT η_strat.

**5.7 Optimierung (Kap. 17).** Fahrweise je 24-h-Fall als **sequentiell linearisiertes MILP** (Pyomo/HiGHS), Netzsensitivitäten aus Finite-Differenz-Probeläufen des nichtlinearen Lösers, Trust-Region 80 kg/s, max. 14 Runden, beste Runde nach **nichtlinearer** Nachrechnung. Zielfunktion **lexikographisch** in drei Stufen: (1) Σ Kunden-Δp-Unterschreitung, (2) Σ HKW-Durchfluss über Erzeugerlimit, (3) Spitzen-Durchfluss, Pumpstrom, Durchsatz, Fahrweisenwechsel (Gewichte 10 €/(kg/s), 120 €/MWh, 0,5 €/MWh, 0,2 €/MW; Stufen 1–2 haben strikten Vorrang). Periodischer Tageszyklus (Füllstand Tagesende ≥ Anfang).

**5.8 pandapipes (Kap. 20).** Aus demselben Datensatz (`NODES`, `E_IDS`, Längen, Durchmesser, Höhen, Multiplikatoren), Vorlauf/Rücklauf getrennt, absolute Drücke = Überdruck + 1,013 bar, Multiplikatoren als wirksame Länge, Pumpen mit konstanter Kennlinie, Reibung Colebrook, k = 0,1 mm.

## 6. Annahmenregister

Legende: **Klasse** D = aus Daten abgeleitet (bestätigt/plausibilisiert), A = Annahme ohne Datenbeleg, P = Vorgabe (Auftrag/Plan), S = Setzung der Studie (Rechenkonvention). **Wirkung**: ● hoch, ◐ mittel, ○ gering (auf die Hauptaussagen). **Sens.** = Sensitivität im Notebook gerechnet (Kap.).

### 6.1 Daten und Einheiten

| ID | Annahme | Wert | Klasse | Ort | Begründung / Prüfung | Wirkung | Sens. |
|---|---|---|---|---|---|---|---|
| D-01 | Druck in ACRON ist **Überdruck** | bar Ü | D | 5, 6.4 | HKW-Rücklauf-Median 8,5 bar gegen Ruhedruck 8,4 bar Ü; Absolut → Faktor 1,013 bar | ● (Siedesicherheit) | – |
| D-02 | Durchfluss in **m³/h** | m³/h | D | 6.4 | Q = V̇ ρ cp ΔT: Verhältnis ≈ 1,04 an 8 Kundenstationen | ◐ | t/h vs. m³/h (Δρ 3–4 %) |
| D-03 | Signalbedeutung HKW/HWW | Bilanzidentitäten | D | 10.5 | HKW-Leistung = Σ vorzeichenbehaftete SL-Leistungen (r = 1,00); HKW-Durchfluss = Σ positive SL-Flüsse; Q_Sek = 0,98 Q_Prim + 0,98 Q_Kessel | ● | – |
| D-04 | Zeitstempel lokal | – | A | 6 | Betreiber nicht bestätigt (Anfrage E1) | ○ | – |
| D-05 | Ausreißerbehandlung | konstante Läufe/Spikes ausgeschlossen (z. B. HWW-Primärspitzen) | S | 6, 12.3 | Qualitätsprüfung Kap. 6.3 | ○ | – |
| D-06 | **Höhen der Stationen** aus Schwachlast-Differenzdrücken | ±3–5 m | D/A | 10.5 | VL/RL-Offsets r = 0,93; Plan-Höhen ±3,5 m (außer GT); Auftraggeber: „Höhe als Annahme“ | ● (absolute Drücke) | Differenzen statt Absolutwerte |
| D-07 | Höhe fehlender Verzweigungsknoten | Mittel der Nachbarknoten (±5 m) | S | 15.2 | rein für absolute Drücke; Δp praktisch unabhängig | ○ | – |
| D-08 | Plan-Maßstab | 1:10 000 → 2,54 m/px | D | 10.6 | gegen YAML-Längen ±7 % | ◐ | Längenband ±12 % (Quelle „G“) |
| D-09 | Trassenlängen aus Bildanalyse (Farbmaske + kürzester Pfad) | je Kante, 90–100 % Deckung | D | 10.6 | Anker aus OCR der Armaturenpositionen | ◐ | Längenband in Kantentabelle |
| D-10 | Längen/DN der Verbundkanten, SL2/SL4a, Teilstücke | Schätzung (Quelle „S“/„K“/„Y“) | A | 10.6 | keine Planbasis | ◐ | k-Kalibrierung gleicht aus |
| D-11 | Westnetz hydraulisch entkoppelt | nur Entnahme | D | 10.7 | σ(RL) = 0,05 bar; Partialkorrelation ≈ 0 | ○ | – |
| D-12 | Lastanteile der Sektionen | kalibriert, **nicht identifizierbar** | A | 13 | nur 7 Stationen gemessen (≈ 21 von ≈ 113 MW) | ● (Ost/Innenstadt) | Ost-Anteil ×0,8/×1,2 (21) |
| D-13 | Schaltzustände 2025 | unbekannt, normal „offen“ | A | 9.3, 10.7 | nicht dokumentiert | ● | S7-1/S7-2 (16) |
| D-14 | Pumpstationen PSS/PSW | Druckgewinn aus Messung, sonst Bypass | D | 12.3 | Median 0 bar, P95 ≈ 1,3 bar | ○ | PSS ohne Förderhöhe (S8e) |

### 6.2 Modell und Kalibrierung

| ID | Annahme | Wert | Klasse | Ort | Begründung / Prüfung | Wirkung | Sens. |
|---|---|---|---|---|---|---|---|
| M-01 | Sektionsmodell statt Straßennetz | 25 Knoten/30 Kanten | S | 10 | Datenlage; Verteilnetze nicht modelliert | ● | Vergleich v0.1–v0.3 |
| M-02 | Rohrrauheit | 0,1 mm | A | 12.2 | YAML 0,5 mm wirkt im Framework nicht | ◐ | 0,05–0,5 mm (21) |
| M-03 | Reibung Swamee–Jain, Übergangsbereich linear | – | S | 12.2 | Test gegen pandapipes-Colebrook (≤ 0,015 bar) | ○ | 20.2 |
| M-04 | Multiplikator k je Leitungsgruppe | 0,2…5 | S | 13 | gleicht Längen-/Durchmesser-/Rauheitsfehler aus; **kein physikalischer Messwert** | ● | ×0,8/×1,2 (21) |
| M-05 | Ost-Kanten (SL3/SL6/SL7) an Kalibriergrenzen | 5,0 / 0,2 / 0,2 | S | 13 | strukturelles Defizit des Ostmodells | ● (Ost) | k = 1 (21) |
| M-06 | AVA und HKW als **Druckränder** (gemessene Drücke); Erzeuger regeln Δp | – | A | 12.4 | Ost-Erzeuger regeln Differenzdruck; im Modell effektive Offsets | ● | A3 der Anfrage |
| M-07 | Ost-Referenzoffsets AVA VL/RL | −0,3 m / +7,7 m (kalibriert) | S | 13 | gleichen Sensorhöhe/Pumpeneffekte aus | ◐ | – |
| M-08 | Messunsicherheit für Kalibrierung | σ_p = 0,3 bar, σ_V = 25 m³/h | A | 13 | inkl. Höhenfehler | ◐ | – |
| M-09 | Kalibrier-/Validierungszeitraum | Jan–Sep / Okt–Dez 2025 | S | 13/14 | zeitlich getrennt; Validierung enthält Extremtage | ○ | 19.7 |
| M-10 | Beethovenpark von Kalibrierung ausgeschlossen | – | S | 13 | 2,9 km DN150-Stichleitung nicht abbildbar | ○ | – |
| M-11 | Kunden-Δp-Bias-Korrektur je Knoten | Median (Messung − Modell) der 10 % Hochlaststunden; ohne Messstelle 0 | S | 16.2 | Differenzdruck-RMSE ≈ 0,3–0,6 bar | ● (absolute Verletzungen) | 19.7 (neu je Kalibrierung) |
| M-12 | Temperaturmodell: U' = 0,3 W/(m K), Boden 10 °C, quasistationär | – | A | 15.3 | Framework-Wert; Boden aus YAML | ◐ (Temperatur) | 0,2–0,4 (21) |

### 6.3 Szenarien und Grenzwerte

| ID | Annahme | Wert | Klasse | Ort | Begründung / Prüfung | Wirkung | Sens. |
|---|---|---|---|---|---|---|---|
| S-01 | Heizkurve | linear: 120 °C @ −10 °C … 90 °C @ +20 °C (T = 110 − Ta, begrenzt 90…120) | P | 8, 16 | Vorgabe; YAML-Kurve als Alternative | ◐ | – |
| S-02 | **Basistag** 14.02.2025 (höchste Tagesleistung ≈ 215 MW; Ta ≈ −3,7 °C) | gemessene Randbedingungen, skaliert auf Auslegungs-Vorlauftemperatur 120 °C | S | 16.1 | Größenordnung der Auslegungs-Tagesleistung der Lastextrapolation (216 MW Mittel/269 MW Spitze) | ● | Lastniveau ±10 % (21) |
| S-03 | Massenströme aus Q = ṁ cp ΔT | höhere Spreizung → kleinere Massenströme | S | 16.1 | Rücklauftemperatur wie am Basistag | ◐ | ±3 K (21) |
| S-04 | Erzeuger GT/BM/HWS | gleiche Massenstromanteile, begrenzt auf 2025-P99,9 | A | 16 | Erzeugerlimits unbekannt (Anfrage A4) | ◐ | – |
| S-05 | **Ungünstige Erzeugerdruckhaltung** | Vorlauf −0,4 bar, Rücklauf +0,25 bar | A | 16.1 | ≈ P5/P95 der Hochlaststunden 2025 | ● | ±0,3 bar (21) |
| S-06 | Kunden-Mindestdifferenzdruck | 1,0 bar | A | 16.1 | 2025: P1 der Stationen ≈ 1,1–1,2 bar; WV640 Δp intern 0,8–1,3 bar; YAML 0,7 bar | ● | 0,8–1,2 bar (21) |
| S-07 | Siedeabstand | p_abs − p_sat ≥ 1 bar | A | 16 | Sicherheitsmarge | ○ | 0,5–2 bar |
| S-08 | Mindest-Lieferungstemperatur | Heizkurve − 10 K | A | 16 | – | ◐ | – |
| S-09 | Erzeugerlimit HKW/AVA | in 2025 beobachtetes Maximum (P99,9) | A | 16 | Kapazitäten unbekannt (A4) | ◐ | – |
| S-10 | Leitungsauslastung | auf v = 2,5 m/s bezogen; bei Trennung auf Transportgrenzen 750/500/300 t/h | A/P | 16 | Transportgrenzen laut Auftrag/WV650 (nicht am Plan geprüft) | ○ | ±20 % |
| S-11 | **Nicht versorgte Wärme** (Näherung) | Anteil 1 − √(Δp/Δp_min) | S | 16.1 | Ventilkennlinie; Rückwirkung vernachlässigt – nur Vergleichsgröße | ◐ | – |
| S-12 | Ausbau | +10/20/30/50 % proportional (alle Sektionen, MAN, West); +30 % nur Ost; +10 % je Sektion einzeln | A | 19 | keine Ausbaudaten (Anfrage D1) | ● | 19.6 |
| S-13 | Schaltzustände S7 | S7-1 Trennung 342.3 (MAN an HKW-Seite), S7-2 Trennung 342.1/001.2 (MAN Ost-Seite); Landungen SL6/SL7 offen | A | 16.3 | aus Plan-Armaturen abgeleitet | ● | beide gerechnet |
| S-14 | Störfälle S8 | GT-Ausfall, AVA-Ausfall, M_SL1_SL2 zu, SL1b/c ×3, PSS ohne Förderhöhe, +8 K Rücklauf, Speicher leer | S | 16.3 | keine Mehrfachausfälle | ◐ | – |
| S-15 | Verstärkungsmaßnahmen | halber Reibungswiderstand (Parallelleitung) Ost bzw. Innenstadtverbund/SL2 | A | 19.8 | Illustration der Hebelwirkung, keine Planung | ◐ | – |

### 6.4 Speicher

| ID | Annahme | Wert | Klasse | Ort | Begründung / Prüfung | Wirkung | Sens. |
|---|---|---|---|---|---|---|---|
| T-01 | Speichertyp | direkt eingebunden, **Druckspeicher**, bis 120 °C | P | 15 | Auftraggeber | ● | – |
| T-02 | Anschlusspunkt MAN | Knoten MAN (T-Abzweig SL5, Arm. 342.x) | A | 10 | Auftraggeber: „MAN-Punkt annehmen“ | ● | Standortvariation (19.4) |
| T-03 | Volumen/Leistung zentral | 5 000 m³ (YAML), 40 MW Ent-/Ladeleistung | A/Y | 15.4 | Leistung nach Anschluss DN300 (≈ 43 MW bei 2,5 m/s) | ● | S9 (19.2) |
| T-04 | Behälter | H = 20 m (Annahme), U-Wert 0,15 W/(m² K), Schichtungsfaktor 0,85 | A | 15.4 | – | ○ | 0,7–0,95 |
| T-05 | Anschluss | DN300, 250 m je Strang, Σζ = 12 | A | 15.4 | = Kundenanschluss MAN_A | ◐ | Länge 100–500 m (21), DN (19.2) |
| T-06 | Pumpe | η = 0,75, Mindest-Drosseldruck 0,5 bar | A | 15.4 | – | ○ | – |
| T-07 | Füllstandsgrenzen | 5–95 % | A | 15.4 | – | ○ | Anfangsfüllstand (19.2) |
| T-08 | Heißtemperatur im Speicher | min(120 °C, Vorlauf) | A | 16 | Annahme: gefüllt zu Tagesbeginn/zyklisch | ◐ | Th (19.2) |
| T-09 | Speicherenergie | 5 000 m³ @ 10 K ≈ 56–58 MWh | D | 12.1 | Test; YAML 84,5 MWh nicht übernommen | ○ | – |

### 6.5 Optimierung und Unsicherheit

| ID | Annahme | Wert | Klasse | Ort | Begründung / Prüfung | Wirkung |
|---|---|---|---|---|---|---|
| O-01 | Lexikographische Priorität Druck > unversorgte Last > Wirtschaft | – | P | 17 | Auftrag | ● |
| O-02 | Gewichte Stufe 3 | 10/120/0,5/0,2 | A | 17 | Platzhalter; Stufen 1–2 dominieren (Gewichtstest in 17.3) | ○ |
| O-03 | Periodischer Tageszyklus, 24 h, ein Tag | – | S | 17 | Mehrtagesbetrieb/Prognose nicht abgebildet | ◐ |
| O-04 | Anschluss-DN-Grenze v ≤ 3 m/s | – | A | 17 | – | ◐ |
| U-01 | Monte-Carlo | 60 Läufe je Fall, σ aus Jacobian (0,05–0,4), 25 % Ost-Strukturvariante, unabhängige Ziehung | S | 21 | **konservativ breit** (Korrelationen ignoriert) | ◐ |
| U-02 | Fahrpläne in der Unsicherheitsanalyse | fest aus Nominal-Optimierung | S | 21 | Betreiber kennt Parameterfehler nicht | ○ |

## 7. Validierung und Modellgüte (abgeleitete Kennzahlen, NDA)

| Größe | Ergebnis |
|---|---|
| Kalibrierung | RMS der normierten Residuen 9,7 → 2,7 (1,0 = Fehler entspricht der Messunsicherheit); nach 37 Auswertungen konvergiert |
| Validierung Okt–Dez 2025 | Vorlaufdruck-RMSE gesamt 0,58 bar (Kalibrierung 0,60); **MAN 0,07 bar**; Mitte/Süd ≈ 0,25 bar; **Ost ≈ 0,8 bar**; Rücklauf 0,64 bar; Kunden-Δp ≈ 0,6 bar (Mitte/Süd), 1,26 (gesamt); Durchfluss HKW 153,9 m³/h (Kal.: 120,8) |
| Hochlast-Differenzdruck | RMSE im Mittel 0,36 bar (Hauptkalibrierung); 0,26 bar mit Zusatzkalibrierung (Kap. 19.7, nicht Hauptmodell) |
| Temperatur | RMSE im Mittel 6 K; Hauptstrang ±1–4 K; Stichleitungen bis 14 K; Netzverlust (nur Hauptleitungen) unterschätzt |
| Eigenmodell ↔ pandapipes | 8 Betriebspunkte (VL+RL): max. Druckabweichung 0,015 bar, Massenstrom ≤ 0,7 kg/s, keine Richtungsabweichung; Temperatur nur am Einzelstrang vergleichbar (Netz konvergiert in pandapipes nicht) |
| Historische Ereignisse | 2025: keine anhaltende Druckkrise; 9 Einzelstunden mit Kunden-Δp < 0,8 bar (2 Nullwerte) |

## 8. Eingebaute Tests und Abnahmeprüfungen

Zelle/Kap. – Test:
* 12.1: Stoffwerte gegen Referenz (ρ, μ, p_sat), Vergleich mit pandapipes-Wasser, Framework-Formeln (`heat_kw_to_mdot_kg_s`, `mdot_to_velocity_m_s`, `pipe_heat_loss_mw`), Speicherbilanz.
* 12.2: Löser: Parallelrohre (analytisch), Ring, Schleifengesetz, Massenbilanz.
* 15.2: Szenario-Engine ≡ kalibrierte Simulation (max. Abweichung 0 m).
* 16.3: S2 ≡ S1 (Anschluss ohne Betrieb), Massenbilanz < 0,01 kg/s, Rückrechnung Leistung–Massenstrom–Spreizung.
* 17: Initialisierungstest (3 Startfahrpläne), Gewichtungstest, Vergleich linear ↔ nichtlinear.
* 20: pandapipes (Druck/Massenstrom/Richtung), Wärmeverlustgesetz am Einzelstrang (analytisch), Energiebilanz des Temperaturmodells.
* 24: **Abnahmeprüfungen (assert)**: S2 ≡ S1; Löser konvergiert in allen Stunden; Massenbilanz; alle Optimierungen optimal und konvergiert; pandapipes < 0,05 bar; Energiebilanz; Heizkurven-Endpunkte; Speicherenergie 56–58 MWh; Paare mit/ohne Speicher; Bestand/Ausbau/vermascht/getrennt; Laden/Entladen getrennt; Pumpen-/Speicherwirkung getrennt; Unsicherheiten vorhanden.

## 9. Bekannte Einschränkungen (für die Prüfung besonders relevant)

1. **Ostbereich** (SL5–SL7, AVA/GT/BM) strukturell unsicher: Kalibrierparameter an Grenzen, Auslastung > 2×; Ost-Aussagen nur ≈ ±1 bar. Der Ostbereich beeinflusst die Maßnahmenrangfolge nur teilweise (Verstärkung Ost).
2. **Absolute Drücke/Verletzungsdauern** hängen von Höhen, Bias-Korrektur, Δp_min und Kalibrierung ab (Defizit im Bestand 15–19 bar·h je nach Kalibrierung); **Differenzen** mit − ohne Speicher sind robuster (Speicherwirkung ≈ +0,1…+0,2 bar auf den kleinsten Kunden-Δp).
3. **Erzeugerdrücke festgehalten.** Die Maßnahme „Druckanhebung“ ist hydraulisch bewertet, ihre Zulässigkeit (Pumpen, Abschaltdrücke) ist **nicht** belegt.
4. **Quasistationär:** keine Druckstöße (Wasserhammer, Armaturenschaltung, Pumpenausfall), keine Netzlaufzeiten, keine dynamische Speicherschichtung.
5. **Ein Tag je Fall (24 h):** kein Mehrtagesbetrieb, keine Prognoseunsicherheit, periodischer Füllstand.
6. **Last- und Ausbauannahmen:** Basistag als Auslegungsniveau; Lastextrapolation ±25 %; Ausbau ohne räumliche Daten.
7. **Speicherstandort:** Sektionsknoten repräsentieren ein Gebiet; Flächen/Genehmigung unbekannt. Innenstadtstandort ist rein hydraulisch bevorzugt.
8. **Unsicherheitsanalyse konservativ breit** (unabhängige Parameterziehung).
9. **Kosten fehlen**; die Rangfolge der Maßnahmen ist rein hydraulisch.
10. **Framework `calion`** wurde nicht verändert: sein Optimierungsmodell enthält weder Höhen, Schleifengesetz noch Speicherpumpe; die Hydraulik dieser Studie ist ausschließlich im Notebook.

## 10. Prüf-Checkliste für Reviewer

| Prüfpunkt | Wo | Worauf achten |
|---|---|---|
| Druck- und Durchflusseinheiten, Höhenbezug | Kap. 6.4, 9.1, 12.3 | Überdruck/Absolut (+1,013 bar), Sensorhöhe, Vorzeichen |
| Topologie und Armaturen | Kap. 9.3, 10, 10.6 | Plausibilität der Verbindungen, v. a. SL5 (K001–JMAN–SL5-Mitte), BM an GT, SL7-Abzweig bei 773, Verbundkanten |
| Trassenlängen/Maßstab | Kap. 10.6 (Overlay-Abbildung, Längenband) | Lage der Anker, Deckung der Pfade |
| Gleichungen | Kap. 11, 12.2 | Druckhöhenformulierung, Pumpen als Druckhöhengewinn, Schleifen |
| Kalibrierbarkeit | Kap. 13 (Identifizierbarkeitstabelle) | Parameter an Grenzen, Standardfehler, Lastanteile |
| Validierung | Kap. 14, 14.1 | Gütekriterien je Region; keine Überanpassung |
| Speicherphysik | Kap. 15.1/15.4 | Gl. 15.1/15.2, Variante A/B, Förderhöhe |
| Szenariobedingungen | Kap. 16.1 | Basistag, Auslegungs-RB, ungünstige Erzeugerdrücke, Grenzwerte, Δp-Bias |
| Optimierung | Kap. 17 | Zielhierarchie, Linearisierungsfehler (Kap. 17.3), Konvergenz |
| Ergebnisse | Kap. 18–19, 22 | Wirkungszerlegung, Standort/Druck/Maßnahmen; Aussagen gedeckt durch Zahlen |
| pandapipes | Kap. 20 | gleicher Datensatz, Abbildung der Multiplikatoren als Länge, Pumpen |
| Unsicherheit | Kap. 21 | Bandbreiten, Modellstruktur (Ost) |
| Daten- und Annahmenlücken | Kap. 23, `Datenanfrage_Betreiber.md` | Priorität-1-Punkte |

Auffällige Stellen, die bewusst zu hinterfragen sind: (a) Kunden-Δp-Grenze 1,0 bar und Bias-Korrektur; (b) k-Multiplikatoren im Ost-Bereich; (c) Ersatz der Druckhaltung der Erzeuger durch feste Druckränder; (d) „nicht versorgte Wärme“ als Näherung; (e) Gleichsetzung Sektionsknoten = Speicherstandort bei der Standortvariation; (f) Basistag als Auslegungsfall.

## 11. Ergebnisartefakte (`results/studie_MAN_UPM/`, nicht versioniert)

Kennzahlen: `szenarien_kennzahlen.csv`, `szenarien_konfiguration.csv`, `vergleich_mit_ohne_speicher.csv`, `wirkungszerlegung.csv`, `s9_auslegungsvariation.csv`, `standortvariation.csv`, `druckanhebung_bedarf.csv`, `druckanhebung_fein.csv`, `ausbauverteilung.csv`, `massnahmenvergleich.csv`, `hochlast_kalibrierung_vergleich.csv`, `sensitivitaet_einzeln.csv`, `monte_carlo.csv`, `pandapipes_vergleich.csv`, `optimierung_protokoll.csv`, `empfehlung.csv`, `datenluecken.csv`, `plan_arbeitspakete.csv`; Texte: `management_summary.md`, `antworten_20_fragen.md`, `plan_weiteres_vorgehen.md`; Kalibrierung: `kalibrierung.json`, `kalibrierung_hochlast.json`; Prüfsummen: `manifest_ergebnisse.csv`; Abbildungen: `abbildungen/*.png` (≈ 29).

## 12. Änderungsprotokoll der Studie (Etappen)

1. Repository-/Dateiinventur, Datenqualität, Heizkurve (Kap. 1–8).
2. Netzmodell v0.1–v0.3, Plangeometrie, Annahmenaudit (Kap. 9–11).
3. Löser, Kalibrierung, Validierung (Kap. 12–14).
4. Speicher, Szenarien, Optimierung, Vergleiche, pandapipes, Unsicherheit, Schlussfolgerungen (Kap. 15–24).
5. Vertiefungen ohne Betreiberdaten: Grafische Zusammenfassung, Plan, Standortvariation, Druckanhebung, Ausbauverteilung, Hochlast-Kalibrierung, Maßnahmenvergleich (Kap. 19.4–19.8, 22.1, 23.1).
