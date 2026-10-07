# CALION Framework — Ergänzungsauftrag: Kapazitäts-Sweep & Publikationsgrafiken (Paper 2)

**Technische Spezifikation für KI-gestützte Code-Implementierung**
Lukas Ruess | Fraunhofer IPA / EEP, Universität Stuttgart | Juli 2026

| ℹ️ **Hinweis an den Agenten** | Dieses Dokument ergänzt `CALION_Paper2_Spezifikation.docx` (Version 1.0, Juni 2026) und baut auf dem bereits implementierten Stand laut `CALION_Paper2_Implementation_Statement.md` (Stand 08.07.2026) auf. Es beschreibt zwei neue, unabhängige Arbeitspakete: (1) ein Dispatch-only-Kapazitäts-Sweep-Modul und (2) die Generierung publikationsreifer Grafiken/Tabellen für das Manuskript. Wo Daten, Schwellenwerte oder Konfigurationsdetails fehlen, MUSST du nachfragen, bevor du Code schreibst oder Grafiken final renderst. Implementiere niemals einen Pfad, Parameter oder eine Szenarioauswahl, die nicht explizit bestätigt wurde. |
|---|---|

---

## 0. Kontext und Zielsetzung

Die Hauptszenariomatrix (46 MILP-Läufe, siehe Implementation Statement §5) liefert `Q̇_WP` und `V_TES` als **Optimierungsergebnis**, nicht als kontrollierte Eingangsgröße. Für die geplante Publikationsabbildung „TAC/LCOH als Funktion von Q̇_WP × V_TES" (Heatmap, analog zu aktuellen HP+TES-Co-Sizing-Studien) ist eine Interpolation aus den 46 Szenarien **methodisch nicht zulässig**, da unterschiedliche Standorte, Heizkurvenstufen und ggf. endogene Standortentscheidungen die Kapazitätswirkung konfundieren würden.

**Lösung:** Ein separates, schlankes Modul `capacity_sweep.py`, das bei **fixierten** Kapazitäten (kein Investitions-MILP, keine Binärvariablen `y_WP`/`y_TES`, keine endogene Standortwahl) ausschließlich den **Betrieb** über ein Kapazitätsraster optimiert (reine Dispatch-LP). Alle anderen Einflussgrößen (Standort, Heizkurve, Abwärmeprofil) bleiben über das gesamte Raster konstant — dadurch wird die Kosten-Kapazitäts-Beziehung ceteris paribus isoliert.

Zusätzlich: Der aus der Hauptoptimierung bekannte MILP-Optimalpunkt (Q̇_WP*, V_TES*) für den gewählten Standort wird als Marker in die Heatmap eingezeichnet — das dient gleichzeitig als **Kreuzvalidierung** (der MILP-Optimalpunkt sollte nahe am Sweep-Minimum liegen; relevant für Abschnitt „2.7 Model Validation" im Manuskript).

---

## Teil A — Modul `capacity_sweep.py`

### A.1 Zweck

Für **einen** repräsentativen Standort je Fallstudie (Stadtbach, Memmingen) und **eine** fixierte Heizkurvenstufe wird ein Raster über `Q̇_WP` und `V_TES` gelöst. Pro Rasterpunkt: eine vollständige Dispatch-Optimierung über T = 8760 h mit fixen Kapazitäten, keine Kapazitäts- oder Standortentscheidung im Solver.

### A.2 Unterschiede zum Hauptmodell (`milp_p2.py`)

| Aspekt | Hauptmodell (`milp_p2.py`) | Sweep-Modell (`capacity_sweep.py`) |
|---|---|---|
| `Q̇_WP`, `V_TES` | Kontinuierliche Optimierungsvariablen | **Fixe Parameter** je Rasterpunkt |
| `y_WP`, `y_TES` | Binäre Aktivierungsvariablen | Fix = 1 (immer aktiv) |
| TES-Standort | Szenario-Loop (S1–S5) oder endogen (S6/S7) | **Ein** fixer Knoten (aus Hauptergebnis übernommen) |
| Heizkurve | 3 Stufen HK0/HK1/HK2 als Szenario-Loop | **Eine** fixe Stufe |
| CAPEX in Zielfunktion | `ANF · (α·x + β·y)`, x als Variable | `ANF · (α·x_fix + β)`, deterministische Konstante je Rasterpunkt |
| Solver-Problemklasse | MILP (Investition + Betrieb) | Reine LP je Rasterpunkt (kein Binär mehr nötig, da y fix) — deutlich schneller |
| Ergebnis | Ein Optimum je Szenario | Eine TAC-/LCOH-Fläche über das Raster |

Alle Betriebs-Constraints (Energiebilanz, SOC-Dynamik, COP-Berechnung, Druck/Temperatur falls L3+ aktiv, Abwärme-Verfügbarkeit) bleiben **unverändert** aus `milp_p2.py` übernommen — es wird nur die Investitionsebene entfernt/fixiert.

### A.3 Rasterdefinition

```python
# Pseudocode — Rastergrenzen werden AUS DEM HAUPTERGEBNIS abgeleitet,
# nicht neu geschätzt.

Q_WP_opt, V_TES_opt = load_main_result(scenario_id=<gewähltes bestes Szenario>)

# Empfehlung: Raster symmetrisch (log- oder linear) um den MILP-Optimalpunkt,
# z.B. Faktor 0.4x bis 1.6x je Dimension, 7x7 = 49 Punkte
q_wp_grid = np.linspace(0.4 * Q_WP_opt, 1.6 * Q_WP_opt, 7)
v_tes_grid = np.linspace(0.4 * V_TES_opt, 1.6 * V_TES_opt, 7)

# Untere Grenze niemals unter Q_WP_min/V_TES_min (Bounds aus Investment-Config)
# Obere Grenze niemals über Q_WP_max/V_TES_max (technische Netzgrenzen)
```

| ⚠️ **Datenbedarf — vor Implementierung klären** |
|---|
| 1. Welches Szenario je Netz gilt als „bestes/repräsentatives" Szenario für den Sweep (aus der fertigen 46-Szenarien-Kampagne — muss also NACH Abschluss der Hauptkampagne bestimmt werden, nicht vorher)? |
| 2. Welche Heizkurvenstufe wird fixiert — Empfehlung HK1 (mittlere Stufe), aber bitte bestätigen. |
| 3. Rastergröße bestätigen: 7×7 (49 Punkte) je Netz als Ausgangspunkt, oder andere Auflösung? |
| 4. Sollen beide Netze denselben Rasterfaktor (0.4×–1.6×) nutzen oder netzspezifisch? |

### A.4 Implementierungsschritte

```
1. main_result_loader.py   — Lädt Q_WP*, V_TES*, Standortknoten, HK-Stufe aus
                              scenarios_kpis.csv für das gewählte Szenario je Netz.
2. capacity_sweep.py        — Baut Rasterpunkte, instanziiert für jeden Punkt eine
                              reduzierte Pyomo-LP (Investitionsblock deaktiviert),
                              löst mit Gurobi (LP, kein MIP-Gap nötig).
3. sweep_kpi.py              — Berechnet TAC, LCOH, OPEX-Split je Rasterpunkt,
                              identisch zur KPI-Definition aus Spec §6.1.
4. Ergebnisexport             results/sweep_{network}_{scenario_id}.csv
                              Spalten: Q_WP, V_TES, TAC, LCOH, OPEX_el, OPEX_gas,
                              OPEX_CO2, CAPEX_annual, feasible (bool)
```

### A.5 Validierungsanforderung (verknüpft mit Hauptmodell-Validierung)

Nach Abschluss des Sweeps: Prüfen, dass der Sweep-Minimalpunkt (in TAC) **nahe** am MILP-Optimalpunkt aus der Hauptoptimierung liegt (Toleranzband vorschlagen, z. B. ±10 % in TAC, ±1 Rasterschritt in Q̇_WP/V_TES — bitte mit mir abstimmen, bevor das als „bestanden/nicht bestanden" ins Manuskript geht). Abweichungen außerhalb der Toleranz sind ein Hinweis auf Inkonsistenzen zwischen Investitions- und Dispatch-Modell und müssen gemeldet werden, **nicht** stillschweigend akzeptiert werden.

---

## Teil B — Grafik- und Tabellengenerierung

### B.1 Allgemeine Vorgaben (für alle Grafiken)

| Vorgabe | Wert |
|---|---|
| Farbschema | Fraunhofer IPA: Primärgrün `#179C7D`, Dunkelblau `#005B7F` — Zusatzfarben für mehr als 2 Kategorien bitte aus der Fraunhofer-CI-Palette ableiten und mir zur Freigabe vorlegen, bevor sie final verwendet werden |
| Ausgabeformat | Vektorgrafik (SVG oder PDF), zusätzlich PNG @ 300 dpi für Word-Zwischenversionen |
| Schriftart | Konsistent mit Fraunhofer-Vorlage (siehe PowerPoint-Template) — bitte Schriftfamilie aus dem vorhandenen PPTX-Template extrahieren und übernehmen |
| Beschriftung | Alle Achsen mit Einheiten, alle Legenden auf Deutsch (Manuskriptsprache final klären — falls Englisch für ECM, Beschriftungen zweisprachig vorbereiten oder Variable für Sprachumschaltung einbauen) |
| Dateibenennung | `fig_{nummer}_{kurzbezeichnung}.svg` bzw. `tab_{nummer}_{kurzbezeichnung}.csv` |
| Ausgabeverzeichnis | **⚠ bitte bestätigen** — Vorschlag: `results/paper2_figures/` |

| ⚠️ **Datenbedarf — vor Rendering klären** |
|---|
| 1. Manuskriptsprache: Deutsch (Entwurf) mit späterer Übersetzung, oder direkt Englisch (da ECM-Zielsprache Englisch ist)? Empfehlung: Achsenbeschriftungen/Legenden von Anfang an auf Englisch, spart einen Übersetzungsdurchgang. |
| 2. Zusatzfarben für >2 Kategorien (z. B. Szenariogruppen S1–S7) — feste Palette vorgeben oder vom Agenten aus der Fraunhofer-CI ableiten lassen? |
| 3. Zielauflösung/Seitenverhältnis je Abbildungstyp — Single-Column (ca. 9 cm Breite) oder Double-Column (ca. 19 cm) laut ECM-Layout? |

### B.2 Einzelspezifikation je Element

#### T1 — Netz-Kenndaten (Tabelle)
- **Inhalt:** Knoten, Rohre, Peak-Last, Jahresenergie, Erzeugerportfolio (Typ, Kapazität, Wirkungsgrad) je Netz, nebeneinander.
- **Quelle:** YAML-Configs (`Stadtbach_topo.yaml`, `Memmingen_P2_base.yaml`).
- **Format:** Reine Tabelle, kein Plot — als CSV + LaTeX/Word-Tabellencode ausgeben.

#### F1 — Modellarchitektur (mehrteilige Abbildung)
- **Panel A:** L3+-Knotenschema (Energiebilanz, Massenstrombilanz an einem Beispielknoten).
- **Panel B:** McCormick-Envelope-Prinzip als kleine Inset-Grafik (4-Ungleichungs-Schema für `W ≈ ṁ·c_p·T`).
- **Quelle:** Kein Datenexport nötig — schematische Zeichnung. **⚠ Bitte mit mir gemeinsam Layout skizzieren, bevor der Agent das final rendert** — das ist die einzige rein konzeptionelle Abbildung ohne Datenbindung, hoher gestalterischer Freiheitsgrad.

#### T2 — Szenario-Matrix-Definition (Tabelle)
- **Inhalt:** Kompakte Fassung der 46-Zeilen-Matrix aus Implementation Statement §B.1.4/§B.2.4 (Szenario-ID, Standort, HK-Stufe, Fallstudie).
- **Quelle:** `scenario_runner.py`-Konfigurationsliste, direkt exportierbar.

#### F2 — Netzkarten mit TES-Kandidatenknoten (2 Panels)
- **Inhalt:** Stadtbach + Memmingen, TES-Standorte S1–S5 farblich hervorgehoben, Produktionsknoten und Wärmepumpen-Knoten markiert.
- **Quelle:** Vorhandene Topologie-Plots als Ausgangsbasis (siehe Folie 4), aber neu gerendert in Publikationsqualität (aktuelle Version ist PowerPoint-Export, nicht vektorbasiert genug).
- **⚠ Datenbedarf:** Koordinaten/Layout-Algorithmus für Knotenpositionen — bereits vorhanden aus bestehendem Netzplot-Code, oder neu zu erzeugen (z. B. via `networkx` mit geographischem oder schematischem Layout)?

#### F3 — Kapazitäts-Heatmap TAC/LCOH (2 Panels, aus Teil A)
- **Inhalt:** Panel A Stadtbach, Panel B Memmingen. X-Achse Q̇_WP [MW], Y-Achse V_TES [m³], Farbwert TAC [€/a] oder LCOH [€/MWh] (bitte festlegen, welche KPI primär gezeigt wird — Vorschlag: LCOH, da normiert und besser vergleichbar). MILP-Optimalpunkt als markierter Stern/Kreuz eingezeichnet.
- **Quelle:** `results/sweep_{network}_{scenario_id}.csv` aus Teil A.
- **Abhängigkeit:** Kann erst gerendert werden, wenn Teil A abgeschlossen ist.

#### T3/T4 — Sammeltabellen alle 46 Szenarien (je Netz eine Tabelle)
- **Inhalt:** Szenario-ID, Standort, HK-Stufe, TAC, LCOH, CO₂-Emissionen, E_TES, Q̇_WP, COP-Jahresmittel.
- **Quelle:** `results/scenarios_kpis.csv`.
- **Format:** Dicht, ggf. mit bedingter Formatierung (z. B. bestes Szenario je Spalte hervorgehoben) — bitte klären, ob farbliche Hervorhebung im Manuskript gewünscht ist (Elsevier akzeptiert i. d. R. schwarz-weiß-taugliche Tabellen, Farbe nur wenn zusätzlich klar lesbar in Graustufen).

#### F4 — k⇔COP⇔V_TES-Kopplungsdiagramm
- **Inhalt:** Weiterentwicklung von Folie 3 — **mit echten Optimierungsergebnissen statt angenommenem Zusammenhang**. Drei Linien (COP rel., TES-Kapazität rel., WP-Kapazität rel.) über Vorlauftemperatur-Niveau (HK0/HK1/HK2), je Netz ein Panel.
- **Quelle:** `results/scenarios_kpis.csv`, gefiltert auf Szenarien mit identischem Standort, nur HK-Stufe variiert (sauberer Vergleich — bitte sicherstellen, dass diese Teilmenge tatsächlich ceteris-paribus ist).
- **Priorität:** Das ist die zentrale wissenschaftliche Abbildung des Papers — höchste Sorgfalt bei Achsenskalierung und Beschriftung.

#### F5 — Kostenreduktion vs. Baseline (gestapelte Balken)
- **Inhalt:** CAPEX-/OPEX-/CO₂-Kostenanteile, bestes Szenario vs. BC-SB/BC-MM.
- **Quelle:** `results/scenarios_kpis.csv` + `results/baseline_kpis.csv`.
- **Format:** Analog zum bereits in Paper 1 verwendeten Cost-Waterfall-Format (Konsistenz zwischen den Papers).

#### F6 — Endogene vs. beste feste Standortwahl
- **Inhalt:** TAC-Differenz zwischen S6/S7 (bzw. S4/S5 Memmingen) und dem jeweils besten festen Szenario S1–S5, plus Angabe des vom Solver gewählten Knotens.
- **Quelle:** `results/scenarios_kpis.csv`.
- **⚠ Hinweis:** Sollte O-7 (fälschliche `status=ok`-Kennzeichnung bei fehlendem Incumbent) bis zur finalen Kampagne nicht behoben sein, MUSS dieses Modul die Konvergenzstatus-Spalte prüfen und nicht-konvergierte Läufe explizit ausschließen, nicht stillschweigend mitplotten.

#### F7 — Sensitivitäts-Tornado
- **Inhalt:** Relative TAC-Änderung [%] bei Parametervariation gemäß Spec §7 (c_el ±30 %, c_CO2 ±50 %, α_WP ±25 %, Q̇_AW,max −50/−100/+50/+100 %, δ_max 0/+50 %, i ±2 Prozentpunkte).
- **Quelle:** `results/sensitivity.csv`.

#### F8 — Räumliches Temperatur-/Druckprofil (mehrteilig)
- **Inhalt:** T_supply und p_supply entlang eines gewählten Trunk-Strangs, über mehrere Stunden/Tageszeiten.
- **Quelle:** `pipe_state_hourly.parquet`, `nodes_state_hourly.parquet`.
- **Doppelfunktion:** Dient sowohl als Ergebnis- als auch als Validierungsabbildung (Monotonie-Check der L3+-Ausbreitung).
- **⚠ Datenbedarf:** Welcher Trunk-Strang je Netz ist repräsentativ (z. B. Hauptleitung von der Erzeugung zum entferntesten Knoten)? Bitte Knotenliste für den Pfad bestätigen.

#### F9 — SOC-Zeitreihe TES
- **Inhalt:** Speicherfüllstand über eine charakteristische Winterwoche und eine Übergangswoche, bestes Szenario je Netz.
- **Quelle:** `results/dispatch_{scen_id}.pkl`.

#### T5 — Validierungstabelle
- **Inhalt:** Energiebilanz-Residuum (max., % vom Jahresbedarf), MIP-Gap-Statistik (Median, Max über alle 46 Läufe), Memmingen-P1-Konsistenzcheck (Soll-OPEX aus Paper 1 vs. Ist-OPEX aus Referenzlauf), COP-Plausibilitätsbereich, Sweep-MILP-Konsistenzcheck aus Teil A.5.
- **Quelle:** `validation.py`-Output, ergänzt um den neuen Sweep-Konsistenzcheck.

---

## Teil C — Empfohlene Implementierungsreihenfolge

| Phase | Modul | Abhängigkeit | Voraussetzung |
|---|---|---|---|
| 1 | Hauptkampagne abschließen (46 Szenarien, KPI-Extraktion) | — | Muss vor allem Weiteren fertig sein |
| 2 | `validation.py` vervollständigen (T5-Datenbasis) | Phase 1 | — |
| 3 | Bestes/repräsentatives Szenario je Netz bestätigen (mit mir) | Phase 1 | **⚠ Nutzerentscheidung nötig** |
| 4 | `capacity_sweep.py` (Teil A) | Phase 3 | Rasterparameter bestätigt |
| 5 | Grafiken T1–T2, F1–F2 (keine Kampagnendaten nötig) | — | Kann parallel zu Phase 1–4 laufen |
| 6 | Grafiken T3–T4, F4–F7, T5 (Kampagnendaten) | Phase 1–2 | — |
| 7 | F8–F9 (räumliche/zeitliche Detaildaten) | Phase 1, Trunk-Strang bestätigt | — |
| 8 | F3 (Heatmap, hängt vom Sweep ab) | Phase 4 | — |
| 9 | Gesamtdurchsicht: Konsistenz Farbschema, Beschriftung, Dateiformate | Alle | — |

---

## Teil D — Offene Punkte, die vor Codebeginn zu klären sind (Zusammenfassung)

1. Bestes/repräsentatives Szenario je Netz für den Sweep (erst nach Kampagnenabschluss bestimmbar).
2. Fixierte Heizkurvenstufe für den Sweep (Vorschlag HK1).
3. Rastergröße und -grenzen (Vorschlag 7×7, Faktor 0.4×–1.6× um MILP-Optimum).
4. Toleranzband für den Sweep-MILP-Konsistenzcheck (Vorschlag ±10 % TAC).
5. Primäre KPI für die Heatmap-Farbskala (Vorschlag LCOH statt TAC).
6. Manuskriptsprache für Achsenbeschriftungen (Empfehlung: direkt Englisch).
7. Farbpalette für >2 Kategorien.
8. Ausgabeverzeichnis für Grafiken.
9. Trunk-Strang-Knotenliste je Netz für F8.
10. Umgang mit O-7 (Konvergenzstatus-Bug) in F6, falls bis dahin nicht behoben.

*Ende des Ergänzungsauftrags — Version 1.0 | Juli 2026 | Lukas Ruess / EEP Stuttgart*
