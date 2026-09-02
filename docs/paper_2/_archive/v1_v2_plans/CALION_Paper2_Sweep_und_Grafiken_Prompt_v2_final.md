# CALION Framework — Ergänzungsauftrag: Kapazitäts-Sweep & Publikationsgrafiken (Paper 2)

**Technische Spezifikation für KI-gestützte Code-Implementierung — Version 2.0 (finalisiert)**
Lukas Ruess | Fraunhofer IPA / EEP, Universität Stuttgart | Juli 2026

| ℹ️ **Hinweis an den Agenten** | Dieses Dokument ergänzt `CALION_Paper2_Spezifikation.docx` (Version 1.0, Juni 2026) und baut auf dem implementierten Stand laut `CALION_Paper2_Implementation_Statement.md` (Stand 13.07.2026) auf. Es beschreibt zwei unabhängige Arbeitspakete: (1) ein Dispatch-only-Kapazitäts-Sweep-Modul und (2) publikationsreife Grafiken/Tabellen für das Manuskript. **Version 2.0 löst alle 10 Punkte aus Teil D der Version 1.0 auf** — Entscheidungen sind unten direkt eingearbeitet, nicht mehr als offene Fragen. Zwei Punkte bleiben als expliziter Arbeitsauftrag an dich (Farbpalette, Trunk-Strang-Herleitung, siehe Teil B.1 und F8) — dort lieferst du einen Vorschlag zur Freigabe, bevor du final renderst. Implementiere niemals einen Pfad, Parameter oder eine Szenarioauswahl, die nicht explizit bestätigt ist. |
|---|---|

---

## 0. Kontext und Zielsetzung

Die Hauptszenariomatrix (46 MILP-Läufe, siehe Implementation Statement §5) liefert `Q̇_WP` und `V_TES` als **Optimierungsergebnis**, nicht als kontrollierte Eingangsgröße. Für die Publikationsabbildung „LCOH als Funktion von Q̇_WP × V_TES" (Heatmap, analog zu aktuellen HP+TES-Co-Sizing-Studien) ist eine Interpolation aus den 46 Szenarien **methodisch nicht zulässig**, da unterschiedliche Standorte, Heizkurvenstufen und ggf. endogene Standortentscheidungen die Kapazitätswirkung konfundieren würden.

**Lösung:** Ein separates, schlankes Modul `capacity_sweep.py`, das bei **fixierten** Kapazitäten (kein Investitions-MILP, keine Binärvariablen `y_WP`/`y_TES`, keine endogene Standortwahl) ausschließlich den **Betrieb** über ein Kapazitätsraster optimiert (reine Dispatch-LP). Alle anderen Einflussgrößen (Standort, Heizkurve, Abwärmeprofil) bleiben über das gesamte Raster konstant — dadurch wird die Kosten-Kapazitäts-Beziehung ceteris paribus isoliert.

Zusätzlich: Der aus der Hauptoptimierung bekannte MILP-Optimalpunkt (Q̇_WP*, V_TES*) für den gewählten Standort wird als Marker in die Heatmap eingezeichnet — das dient gleichzeitig als **Kreuzvalidierung** (der MILP-Optimalpunkt sollte nahe am Sweep-Minimum liegen; relevant für Abschnitt „2.7 Model Validation" im Manuskript, Ziel-Journal Energy Conversion and Management, 9.000 Wörter / max. 15 Abbildungen+Tabellen im Haupttext).

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
| Heizkurve | 3 Stufen HK0/HK1/HK2 als Szenario-Loop | **Eine** fixe Stufe (**HK1**, siehe A.3) |
| CAPEX in Zielfunktion | `ANF · (α·x + β·y)`, x als Variable | `ANF · (α·x_fix + β)`, deterministische Konstante je Rasterpunkt |
| Solver-Problemklasse | MILP (Investition + Betrieb) | Reine LP je Rasterpunkt (kein Binär mehr nötig, da y fix) — deutlich schneller |
| Ergebnis | Ein Optimum je Szenario | Eine TAC-/LCOH-Fläche über das Raster |

Alle Betriebs-Constraints (Energiebilanz, SOC-Dynamik, COP-Berechnung, Druck/Temperatur falls L3+ aktiv, Abwärme-Verfügbarkeit) bleiben **unverändert** aus `milp_p2.py` übernommen — es wird nur die Investitionsebene entfernt/fixiert.

### A.3 Rasterdefinition — FINALISIERT

```python
# Rastergrenzen werden AUS DEM HAUPTERGEBNIS abgeleitet, nicht neu geschätzt.

Q_WP_opt, V_TES_opt = load_main_result(scenario_id=<bestes Szenario, siehe A.6>)

# Bestätigt: 7x7-Raster, Faktor 0.4x-1.6x, netzweit einheitlich (nicht netzspezifisch)
q_wp_grid = np.linspace(0.4 * Q_WP_opt, 1.6 * Q_WP_opt, 7)
v_tes_grid = np.linspace(0.4 * V_TES_opt, 1.6 * V_TES_opt, 7)

# Untere Grenze niemals unter Q_WP_min/V_TES_min (Bounds aus Investment-Config)
# Obere Grenze niemals über Q_WP_max/V_TES_max (technische Netzgrenzen)
```

Fixierte Heizkurvenstufe: **HK1** (mittlere Stufe), für beide Netze einheitlich.

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

### A.5 Validierungsanforderung — FINALISIERT

Nach Abschluss des Sweeps: Prüfen, dass der Sweep-Minimalpunkt (in TAC) nahe am MILP-Optimalpunkt aus der Hauptoptimierung liegt. **Bestandene Kreuzvalidierung erfordert BEIDE Kriterien gleichzeitig (verschärfte Variante):**

1. TAC-Abweichung ≤ **±10 %**, UND
2. Rasterabstand ≤ **±1 Rasterschritt** in Q̇_WP UND V_TES gegenüber dem MILP-Optimum.

Erfüllt nur eines der beiden Kriterien → als "grenzwertig" markieren, nicht als "bestanden" werten. Abweichungen außerhalb der Toleranz sind ein Hinweis auf Inkonsistenzen zwischen Investitions- und Dispatch-Modell und müssen im Validierungsbericht (T5) explizit gemeldet werden, **nicht** stillschweigend akzeptiert werden.

### A.6 Auswahl des repräsentativen Szenarios je Netz — **NOCH OFFEN**

⚠ **Dieser Punkt kann erst nach Abschluss der Hauptkampagne (46 Szenarien, vollständige KPI-Extraktion) entschieden werden.** Frage aktiv nach, sobald `scenarios_kpis.csv` vollständig vorliegt — nicht vorher raten oder ein vorläufiges Szenario annehmen. Bis dahin: Teil A kann implementiert und mit einem Dummy-/Testszenario (z. B. ein einzelner abgeschlossener Lauf) verifiziert werden, aber der finale Sweep-Lauf wartet auf diese Bestätigung.

---

## Teil B — Grafik- und Tabellengenerierung

### B.1 Allgemeine Vorgaben (für alle Grafiken) — FINALISIERT

| Vorgabe | Wert |
|---|---|
| Farbschema | Fraunhofer IPA: Primärgrün `#179C7D`, Dunkelblau `#005B7F`. **Für >2 Kategorien (z. B. S1–S7): leite eine Palette per HSL-Interpolation zwischen beiden Leitfarben ab (ggf. 1–2 Zwischentöne), prüfe CMYK-Tauglichkeit und Unterscheidbarkeit in Graustufen-/Farbenblindheits-Simulation. Liefere Hex-Liste + Vorschau-Farbstreifen zur Freigabe, BEVOR die Palette in F2, F4 oder F7 verwendet wird.** |
| Ausgabeformat | Vektorgrafik (SVG oder PDF), zusätzlich PNG @ 300 dpi für Word-Zwischenversionen |
| Schriftart | Konsistent mit Fraunhofer-Vorlage — Schriftfamilie aus dem vorhandenen PPTX-Template extrahieren und übernehmen |
| Sprache | **Englisch**, direkt (Zielsprache ECM) — kein zweisprachiger Umschaltmechanismus nötig |
| Seitenlayout | ECM-Layout beachten: Single-Column (~9 cm) oder Double-Column (~19 cm) je nach Abbildungskomplexität — Vorschlag pro Abbildung machen, mit KPI-Element-Budget abgleichen (max. 15 Abbildungen+Tabellen im Haupttext gesamt) |
| Dateibenennung | `fig_{nummer}_{kurzbezeichnung}.svg` bzw. `tab_{nummer}_{kurzbezeichnung}.csv` |
| Ausgabeverzeichnis | `results/paper2_figures/` |

### B.2 Einzelspezifikation je Element

#### T1 — Netz-Kenndaten (Tabelle)
- **Inhalt:** Knoten, Rohre, Peak-Last, Jahresenergie, Erzeugerportfolio (Typ, Kapazität, Wirkungsgrad) je Netz, nebeneinander.
- **Quelle:** YAML-Configs (`Stadtbach_topo.yaml`, `Memmingen_P2_base.yaml`).
- **Format:** Reine Tabelle, kein Plot — als CSV + LaTeX/Word-Tabellencode ausgeben.

#### F1 — Modellarchitektur (mehrteilige Abbildung)
- **Panel A:** L3+-Knotenschema (Energiebilanz, Massenstrombilanz an einem Beispielknoten).
- **Panel B:** McCormick-Envelope-Prinzip als kleine Inset-Grafik (4-Ungleichungs-Schema für `W ≈ ṁ·c_p·T`).
- **Quelle:** Kein Datenexport nötig — schematische Zeichnung. **Layout gemeinsam mit dem Nutzer skizzieren, bevor final gerendert wird** — einzige rein konzeptionelle Abbildung ohne Datenbindung, hoher gestalterischer Freiheitsgrad.

#### T2 — Szenario-Matrix-Definition (Tabelle)
- **Inhalt:** Kompakte Fassung der 46-Zeilen-Matrix aus Implementation Statement §B.1.4/§B.2.4 (Szenario-ID, Standort, HK-Stufe, Fallstudie).
- **Quelle:** `scenario_runner.py`-Konfigurationsliste, direkt exportierbar.

#### F2 — Netzkarten mit TES-Kandidatenknoten (2 Panels)
- **Inhalt:** Stadtbach + Memmingen, TES-Standorte S1–S5 farblich hervorgehoben (siehe B.1-Palette), Produktionsknoten und Wärmepumpen-Knoten markiert.
- **Quelle:** Vorhandene Topologie-Plots als Ausgangsbasis, neu gerendert in Publikationsqualität (vektorbasiert, nicht PowerPoint-Export).
- Koordinaten/Layout-Algorithmus: sofern kein bestehender Netzplot-Code mit geeigneten Positionen vorliegt, `networkx` mit schematischem Layout verwenden.

#### F3 — Kapazitäts-Heatmap LCOH (2 Panels, aus Teil A)
- **Inhalt:** Panel A Stadtbach, Panel B Memmingen. X-Achse Q̇_WP [MW], Y-Achse V_TES [m³], Farbwert **LCOH [€/MWh]** (primäre KPI, bestätigt). MILP-Optimalpunkt als markierter Stern/Kreuz eingezeichnet. TAC optional als Sekundärinfo (z. B. Tooltip/Anhang), nicht als zweite Hauptachse.
- **Quelle:** `results/sweep_{network}_{scenario_id}.csv` aus Teil A.
- **Abhängigkeit:** Kann erst gerendert werden, wenn Teil A abgeschlossen ist (→ hängt an A.6).

#### T3/T4 — Sammeltabellen alle 46 Szenarien (je Netz eine Tabelle)
- **Inhalt:** Szenario-ID, Standort, HK-Stufe, TAC, LCOH, CO₂-Emissionen, E_TES, Q̇_WP, COP-Jahresmittel.
- **Quelle:** `results/scenarios_kpis.csv`.
- **Format:** Dicht; bedingte Formatierung nur, wenn zusätzlich klar lesbar in Graustufen (Elsevier-Konvention).

#### F4 — k⇔COP⇔V_TES-Kopplungsdiagramm
- **Inhalt:** Weiterentwicklung von Folie 3 — **mit echten Optimierungsergebnissen statt angenommenem Zusammenhang**. Drei Linien (COP rel., TES-Kapazität rel., WP-Kapazität rel.) über Vorlauftemperatur-Niveau (HK0/HK1/HK2), je Netz ein Panel.
- **Quelle:** `results/scenarios_kpis.csv`, gefiltert auf Szenarien mit identischem Standort, nur HK-Stufe variiert (sauberer Ceteris-paribus-Vergleich — Teilmenge vor Verwendung verifizieren).
- **Priorität:** Zentrale wissenschaftliche Abbildung des Papers — höchste Sorgfalt bei Achsenskalierung und Beschriftung, höchste Design-Priorität insgesamt.

#### F5 — Kostenreduktion vs. Baseline (gestapelte Balken)
- **Inhalt:** CAPEX-/OPEX-/CO₂-Kostenanteile, bestes Szenario vs. BC-SB/BC-MM.
- **Quelle:** `results/scenarios_kpis.csv` + `results/baseline_kpis.csv`.
- **Format:** Analog zum in Paper 1 verwendeten Cost-Waterfall-Format (Konsistenz zwischen den Papers).

#### F6 — Endogene vs. beste feste Standortwahl
- **Inhalt:** TAC-Differenz zwischen S6/S7 (bzw. S4/S5 Memmingen) und dem jeweils besten festen Szenario S1–S5, plus Angabe des vom Solver gewählten Knotens.
- **Quelle:** `results/scenarios_kpis.csv`.
- **Statusprüfung (O-7):** O-7 ist laut Implementation Statement (08.07.2026) behoben und verifiziert. **Trotzdem defensiv umsetzen:** jeden Datenpunkt mit `status != 'ok'` (bzw. `no_incumbent`) explizit ausschließen/grau markieren, statt `obj`-Werte ungeprüft zu plotten.

#### F7 — Sensitivitäts-Tornado
- **Inhalt:** Relative TAC-Änderung [%] bei Parametervariation gemäß Spec §7 (c_el ±30 %, c_CO2 ±50 %, α_WP ±25 %, Q̇_AW,max −50/−100/+50/+100 %, δ_max 0/+50 %, i ±2 Prozentpunkte).
- **Quelle:** `results/sensitivity.csv`.

#### F8 — Räumliches Temperatur-/Druckprofil (mehrteilig)
- **Inhalt:** T_supply und p_supply entlang eines gewählten Trunk-Strangs, über mehrere Stunden/Tageszeiten.
- **Quelle:** `pipe_state_hourly.parquet`, `nodes_state_hourly.parquet`.
- **Doppelfunktion:** Dient sowohl als Ergebnis- als auch als Validierungsabbildung (Monotonie-Check der L3+-Ausbreitung).
- **Trunk-Strang-Herleitung — Arbeitsauftrag an den Agenten (nicht vom Nutzer vorgegeben):**
  Bestimme je Netz algorithmisch den hydraulisch längsten Pfad (größte kumulierte Rohrlänge oder größte kumulierte ΔT_pipe, beides angeben) vom Haupterzeugerknoten zum am weitesten entfernten Abnehmerknoten, z. B. via `networkx` auf der gewichteten Topologie (`Stadtbach_topo.yaml`, `Memmingen_P2_base.yaml`). Bei mehreren ähnlich langen Pfaden (< 5 % Unterschied): alle Kandidaten auflisten, nicht automatisch entscheiden. Liefere je Netz Knotenliste, kumulierte Länge [m], kumuliertes ΔT_pipe [K] und eine kleine Übersichtsgrafik (Pfad im Netzplan hervorgehoben) **zur Bestätigung durch den Nutzer, vor finalem Rendering von F8.**

#### F9 — SOC-Zeitreihe TES
- **Inhalt:** Speicherfüllstand über eine charakteristische Winterwoche und eine Übergangswoche, bestes Szenario je Netz.
- **Quelle:** `results/dispatch_{scen_id}.pkl`.

#### T5 — Validierungstabelle
- **Inhalt:** Energiebilanz-Residuum (max., % vom Jahresbedarf), MIP-Gap-Statistik (Median, Max über alle 46 Läufe), Memmingen-P1-Konsistenzcheck (Soll-OPEX aus Paper 1 vs. Ist-OPEX aus Referenzlauf), COP-Plausibilitätsbereich, Sweep-MILP-Konsistenzcheck aus Teil A.5 (beide Kriterien: TAC ±10 % UND ±1 Rasterschritt).
- **Quelle:** `validation.py`-Output, ergänzt um den Sweep-Konsistenzcheck.

---

## Teil C — Empfohlene Implementierungsreihenfolge

| Phase | Modul | Abhängigkeit | Voraussetzung |
|---|---|---|---|
| 1 | Hauptkampagne abschließen (46 Szenarien, KPI-Extraktion) | — | Muss vor allem Weiteren fertig sein |
| 2 | `validation.py` vervollständigen (T5-Datenbasis) | Phase 1 | — |
| 3 | Bestes/repräsentatives Szenario je Netz bestätigen (mit dem Nutzer) | Phase 1 | ⚠ Nutzerentscheidung nötig, siehe A.6 |
| 4 | `capacity_sweep.py` (Teil A) | Phase 3 | Rasterparameter bestätigt (✅ erledigt) |
| 5 | Grafiken T1–T2, F1–F2 (keine Kampagnendaten nötig) | — | Kann sofort parallel starten |
| 5b | Trunk-Strang-Herleitung für F8 (nur Topologie-Configs nötig) | — | Kann sofort parallel starten, Ergebnis dann zur Freigabe vorlegen |
| 5c | CI-Farbpalette ableiten (B.1) | — | Kann sofort parallel starten, Ergebnis dann zur Freigabe vorlegen |
| 6 | Grafiken T3–T4, F4–F7, T5 (Kampagnendaten) | Phase 1–2 | — |
| 7 | F8–F9 (räumliche/zeitliche Detaildaten) | Phase 1, Trunk-Strang bestätigt (5b) | — |
| 8 | F3 (Heatmap, hängt vom Sweep ab) | Phase 4 | — |
| 9 | Gesamtdurchsicht: Konsistenz Farbschema, Beschriftung, Dateiformate | Alle | — |

---

## Teil D — Status der Klärungspunkte (alle aus v1.0 aufgelöst)

| # | Punkt | Ergebnis |
|---|---|---|
| 1 | Bestes Szenario je Netz | ⏳ Offen — siehe A.6, nach Kampagnenabschluss |
| 2 | Heizkurvenstufe Sweep | ✅ HK1 |
| 3 | Rastergröße | ✅ 7×7, Faktor 0.4×–1.6×, netzweit einheitlich |
| 4 | Toleranzband Konsistenzcheck | ✅ ±10 % TAC UND ±1 Rasterschritt (beide Kriterien) |
| 5 | Primäre Heatmap-KPI | ✅ LCOH |
| 6 | Manuskriptsprache | ✅ Englisch |
| 7 | Farbpalette >2 Kategorien | 🔶 Agent-Vorschlag, siehe B.1 |
| 8 | Ausgabeverzeichnis | ✅ `results/paper2_figures/` |
| 9 | Trunk-Strang F8 | 🔶 Agent leitet algorithmisch her, siehe F8 |
| 10 | O-7-Umgang in F6 | ✅ behoben, defensive Statusprüfung trotzdem eingebaut |

*Ende der Spezifikation — Version 2.0 | Juli 2026 | Lukas Ruess / EEP Stuttgart. Bereit zur Übergabe an den Coding Agenten.*
