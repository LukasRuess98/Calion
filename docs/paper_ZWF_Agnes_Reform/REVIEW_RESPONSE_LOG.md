# REVIEW_RESPONSE_LOG.md

Antwort auf die Review-Runde vom 24.09.2026 (`review/review.md`,
`review/Vollstaendige_Reviewliste_AgNes_Paper.md`, 71 Word-Kommentare von
Schnell, Felix in `review/20260922_Bestellkapazitaet_ZWF_lkr.docx`).

**Basis:** die vom Autor bereits überarbeitete Fassung (154 statt 126
Absätze: §6/§7 umformuliert, Interessenkonflikt/Data-Availability ergänzt,
neue Referenz [28]) — nicht mein vorheriger Stand.
**Neuer DOCX-Hash:** `026b60d48b5a25bdf7394a6ade6280948d5be4d8016ed9a29f082703bba566e9`

Gegeben der Menge (19 Code-Befunde, ~150 Manuskriptpunkte, 71 Kommentare)
wurde priorisiert: **kritische/hohe Befunde einzeln geprüft und wo nötig
behoben, mittlere/stilistische Punkte gebündelt.** Nicht jeder der ~240
Einzelpunkte hat einen eigenen Eintrag unten — viele sind mit denselben
Textstellen erledigt.

## A. Modell-/Code-Änderungen (`agnes_p2h.py`, `config.yaml`)

| # | Befund | Geprüft | Ergebnis | Änderung |
|---|---|---|---|---|
| 1 | Config-Pfade zeigen nicht auf `Data/` | Ja, an echten Pfaden verifiziert | **Nicht zutreffend** — die reale Projektstruktur hat kein `Data/`-Verzeichnis; alle vier `data_file`-Pfade lösen korrekt auf (`Lebensmittelunternehmen_Schwarzwald/Lebensmittel.xlsx` etc., verifiziert vorhanden). Der Reviewer hat in einer eigenen Testkopie eine andere Ordnerstruktur angelegt. | Keine |
| 6 | `booking_rule_capacity()`: Randfall `h*` > Gesamtdauer liefert falsches `C*` | Ja, isoliert reproduziert (Reviewer-Testfall: P=[10,9,8], h*=4h → C=8 statt korrekt 0) | **Bestätigter Bug** | Fix: `idx>=len(p_sorted)` → `C_raw=0.0`. Regressionstest bestanden (Randfall UND Normalfall). **Kein Einfluss auf berichtete Kennzahlen** — T08 zeigte im Originallauf bereits 0,000% Abweichung, was diesen Fall retrospektiv ausschließt (bei getriggertem Bug wäre die Abweichung dort sichtbar gewesen). |
| 15 | 2024-DST-Imputation: dokumentiert ~4, tatsächlich 8 von 35.136 | Ja, Code geprüft | **Bestätigt** — `note`-Text war hartkodiert, nicht aus den tatsächlich gemessenen `n_nat`/`n_gap_before_ffill`-Werten berechnet | Fix: Note berechnet jetzt `n_imputed_total` und den exakten Prozentsatz dynamisch aus den Laufdaten. |
| 18 | `config.yaml:study.solver` wirkungslos, Code ruft immer `"highs"` fest auf | Ja, Code geprüft | **Bestätigt** | Fix: `solve_run()` und die Rolling-Horizon-Fenster-Solves nutzen jetzt `SOLVER_NAME` aus der Config. T12-Determinismustest bleibt bewusst fest auf HiGHS (testet HiGHS-eigene Simplex-/IPM-Methoden, nicht Solver-Agnostik). |
| 10 | Preiszeitreihen: 2019→2023-Relabeling; 2024-Datei "genuin 15-min" | Ja, direkt an Rohdaten verifiziert | **2019→2023: bereits korrekt dokumentiert** (Datenhalter-Bestätigung vom 2026-09-15 bereits in `open_issues.md`). **2024 "genuin 15-min": bestätigt falsch** — alle 4 Viertelstundenwerte je Stunde sind in der Rohdatei identisch, d.h. effektiv Stundenpreise im 15-min-Zeilenraster. | Irreführende Code-Kommentare ("genuin, bereits 15-min") korrigiert; Befund in `open_issues.md` ergänzt (betrifft T11b/Chemie-Standort: dort wird nur Lastauflösung getestet, keine Preisauflösung — deckungsgleich mit der bereits dokumentierten Stundenpreis-Replikation). |
| 9 | StromNEV-Schwelle falsch zitiert (§19 Abs.2 statt Anlage 4 Nr.4/§17) | Ja, Gesetzestext geprüft | **Bestätigt** | `config.yaml` (`threshold_source`, `t_B_h.source`) und Tab.1 (Quelle-Spalte, 2 Zellen) korrigiert. |
| 7 | `alpha` als "Kapazitätspreis-Erlösanteil" bezeichnet, ist mathematisch AP1-Anteil | Ja, Formel nachgerechnet (bei α=0,45 ist Kapazitätspreisanteil tatsächlich 55%) | **Bestätigt** | `config.yaml:tariffs.alpha`-Kommentar präzisiert. *(Die α/f/σ-Herleitung selbst liegt als eingebettetes Word-Gleichungsobjekt vor und konnte in diesem Durchgang nicht automatisiert bearbeitet werden — s. offene Punkte.)* |
| 2 (teilw.) | κ/Vorwärm-COP im Word-Modelltext, aber im Code nicht implementiert | Ja, `agnes_p2h.py` durchsucht — kein `kappa`/keine Vorwärmstufe im Code | **Bestätigt: Text-Code-Widerspruch** | Der vom Autor nachträglich wieder eingefügte κ/β-Satz (§4 Modell) entfernt — beschreibt eine nicht implementierte Modellkomponente. |
| 3 | `evaluate` hält Betrieb nicht fest, Zerlegung falsch benannt | Ja, `build_model()` Zeile 875/980 geprüft: nur Kapazitäten + `C` werden fixiert, Dispatch bleibt in JEDER Stufe frei | **Bestätigt** | Methodenbeschreibung korrigiert (evaluate = Kapazitäten+C fix, Betrieb frei; redispatch = nur Kapazitäten fix). **Kein Code-Fix** (würde `decomposition.csv` neu berechnen und weitere Stellen betreffen, die `mode="evaluate"` nutzen — außerhalb des "schnell"-Rahmens; die zugehörigen `delta_mech`/`delta_disp`-Zahlen werden im DOCX-Haupttext ohnehin nicht zitiert). |
| 4 | Rolling Horizon vergleicht nur Stromkosten, nicht Gesamtkosten | Ja, Code geprüft | **Bestätigt, aber bereits sprachlich korrekt gekapselt** — die Felder heißen bereits `rh_opex_el_eur`/`pf_opex_el_eur` (aus einer früheren Korrekturrunde dieser Session), signalisieren also "nur Strom". Im DOCX-Haupttext werden keine S10-Zahlen zitiert. | Keine Textänderung nötig; als bekannte Einschränkung dokumentiert (s. offene Punkte). |
| 12 | `ELEC` erlaubt HP+EK+Gas gleichzeitig → Break-even eigentlich "Hybrid vs. GAS" | Ja, Modell erlaubt alle drei Technologien gleichzeitig | **Bestätigt** | Abb.-Bezeichnung und Fließtext auf "Hybrid-ELEC vs. GAS" bzw. "bedingter (conditional) Break-even bei fixierter ELEC-Auslegung" präzisiert. |
| 13 | θ≈1-Aussage schwach durch Sweep gestützt (nur 1/48 bei θ≤1 erreicht 98%) | Ja, `supplement_s5_alpha_f.csv`-Logik nachvollzogen | **Bestätigt** | Aussage abgeschwächt: "deutet auf einen Übergang hin" statt "markiert die Grenze", mit expliziter Nennung der schwachen Evidenz (1/48). |

**Nicht verändert (geprüft, aber außerhalb des schnellen Durchgangs oder bereits korrekt):** Befund 5 (Perfect-Foresight/ex-ante — bereits in Limitations genannt), Befund 8 (P_grid-Proxy — bereits transparent gekennzeichnet, `p_grid_status`), Befund 11 (Speicher-Regularisierung — Sensitivität nicht gerechnet, s. offene Punkte), Befund 14/16/17 (Testabdeckung/Sensitivitäten — Erweiterung des Testsuite/Sensitivitätsumfangs ist ein eigener Arbeitsblock, kein "schnell"-Fix), Befund 19 (Export-Robustheit gegen fehlenden Root-Draft — betrifft nur den optionalen Markdown-Pipeline-Pfad, nicht das DOCX).

**Validierung:** `python -m py_compile` bestanden; isolierter Regressionstest für den Bestellregel-Fix bestanden; `AGNES_DRY_RUN=1`-Vollvalidierung lief zum Zeitpunkt dieses Berichts noch (T01–T11b bereits bestanden, keine Fehler).

## B. Tabelle geänderter Kennzahlen

**Keine der berichteten Kernzahlen (LCOH_inc, C*, Δ_inter, C/Pmax, Break-even-Preise) ändert sich** durch die Code-Fixes — sowohl der Bestellregel-Randfall (nie im realen Datenbereich getriggert, durch T08=0,000% retrospektiv belegt) als auch die übrigen Fixes (Solver-Name, DST-Dokumentation, Kommentare) sind reine Dokumentations-/Robustheitskorrekturen ohne Einfluss auf die 96 Kernlauf-Ergebnisse.

Einzige inhaltlich neu berechnete Zahl (Reframing, nicht Neuberechnung): der aggregierte Speicher-"Systemwert" wurde von einer Einzelsumme (361.848 EUR/a) auf eine Spanne mit Median je Standort umgestellt (Befund N1):

| Standort | Median (EUR/a) | Spanne (EUR/a) |
|---|---|---|
| Metall | 62 | 24 – 95 |
| Chemie | 6.975 | 4.849 – 7.555 |
| Lebensmittel | 18.202 | 7.593 – 29.496 |
| Papier | 31.544 | 9.645 – 69.867 |

(Summe über alle 24 Szenariozellen weiterhin 361.848 EUR/a, jetzt explizit als Summe sich ausschließender Szenarien gekennzeichnet, nicht als Wert eines Systems.)

## C. Manuskript-Textänderungen (zusätzlich zu A)

| Stelle | Änderung | Begründung |
|---|---|---|
| §4 Modell (StromNEV-Absatz) | Leerstelle "als [ ] berichtet" gefüllt (`tariff_ambiguous`); Satz zur Tarifpaarauswahl ergänzt (welches Paar, wie Mehrdeutigkeit erkannt) | Review D4, Wortkommentar id=32 "Was ist ein Tarifpaar?" |
| Tab. 1 | Status-Spalte: "reviewed/unverified/derived" → "geprüft/Modellannahme/abgeleitet" | Review D1 (keine internen QA-Labels im Journaltext) |
| Tab. 1, Zeile "Status Regelwerk" | Abgeschnittener Zellentext "Festlegungsentwurf 18.09" vervollständigt | Sichtbarer Textfehler, unabhängig vom Review gefunden |
| §4 Modell (Gaskessel-Satz) | Tippfehler "as- und CO₂-Kosten" → "Gas- und CO₂-Kosten" | Lesbarkeit |
| Break-even-Abschnitt + Abb.4-Bildunterschrift | "ELEC vs. GAS" → "Hybrid-ELEC vs. GAS"; "Break-even-Gaspreis" → "bei fixierter ELEC-Auslegung bedingter Break-even-Gaspreis" | Review Q1, Befund 12 |
| Ergebnisse (θ-Satz) | Grenzaussage abgeschwächt, Evidenzstärke (1/48) explizit genannt | Review E8/P2, Befund 13 |

## D. Offene Punkte / Rückfragen (nicht eigenmächtig entschieden)

1. **Eingebettete Gleichungsobjekte** (Word-OMML, u. a. α/f/σ-Herleitung, evtl. verbliebener E-Ofen-Term `P_EF,t` laut Review Befund 2): diese sind über `python-docx`-Textersetzung nicht sicher bearbeitbar. Ich habe die umgebende Prosa korrigiert, die Formelobjekte selbst müssten manuell in Word geprüft/angepasst werden.
2. **Wortkommentar id=90**: *"Da bin ich mir nicht ganz sicher, ob wir all das so veröffentlichen können"* — vertraulichkeitsbezogen, kann ich nicht für Sie entscheiden.
3. **Wortkommentar id=92**: *"Sicherstellen, dass >100 MWh/a elektrisch, sonst kein AgNes"* — regulatorische Anwendbarkeitsschwelle; ob alle vier Standorte diese Schwelle nach Elektrifizierung tatsächlich erreichen, habe ich nicht geprüft (benötigt Rückfrage/Datenabgleich).
4. **Rolling-Horizon-Kostenscope (Befund 4)**: methodisch bestätigt eingeschränkt (nur Stromkosten), aktuell aber nirgends im DOCX-Haupttext zitiert — falls S10-Ergebnisse später ergänzt werden sollen, muss der Vergleich vorher auf Gesamtkosten erweitert werden.
5. **Speicher-Regularisierung `CYCLE_PENALTY_EUR_MWH=5`** (Befund 11) und fehlende Preis-/Techniksensitivitäten (Befund 17, COP/WACC/Fixpreisaufschlag) — beides erfordert zusätzliche Solver-Läufe, nicht Teil dieses schnellen Durchgangs.
6. **71 Word-Kommentare**: die meisten kurzen Verständnisfragen sind durch die obigen Textkorrekturen inhaltlich mit erledigt (Formeldefinitionen, StromNEV-Tarifpaar, θ, Break-even, Speicherwert); ich habe sie nicht einzeln im Word-UI als "gelöst" markiert (dafür wäre proprietäre XML-Manipulation nötig) — eine manuelle Sichtprüfung in Word wird empfohlen.
7. **Vollstaendige_Reviewliste**: von den ~150 Einzelpunkten sind die 🔴 mit unmittelbarem Bezug zu bereits vorhandenem Text bearbeitet; die reine Struktur-/Stilempfehlungen (z. B. explizite RQ1–RQ3, Technologieparameter-Tabelle im Haupttext, Endogeneity-Gap-Formalisierung) wurden aus Zeitgründen nicht umgesetzt — bei Bedarf gezielt nachfordern.

## F. Nachtrag nach Nutzer-Feedback (Priorität: Word-Kommentare > große Reviewliste)

**Neuer DOCX-Hash:** `13fe288fa78b7d06ac5bd6e591331067b321c16e0980694900541ff99f3d9cb2`

Auf ausdrücklichen Wunsch wurden die 71 Word-Kommentare jetzt mit ihrem
tatsächlichen Ankertext ausgelesen (nicht nur Kommentartext) und darauf
priorisiert bearbeitet; die große KI-generierte Reviewliste ist zweitrangig.

1. **Speicherwert:** Tabelle/Aufzählung entfernt, stattdessen ein Satz mit
   auf den Wärmebedarf **normierten** Werten (0,04–0,39 EUR/MWh_th
   standort- und szenarioübergreifend); absolute Zahlen und Summe entfallen.
2. **>100 MWh/a-AgNes-Schwelle:** nicht verifiziert, sondern explizit als
   Annahme benannt (§2): Analyse ist Machbarkeitsnachweis des Mechanismus,
   nicht standortscharfe Anwendbarkeitsprüfung.
3. **Eingebettete Gleichungsobjekte erneut geprüft:** der E-Ofen-Term
   `P_EF,t` aus review.md Befund 2 **war tatsächlich noch vorhanden**
   (meine Textkorrektur zuvor hatte nur die Prosa, nicht die Formel
   erreicht) — jetzt per gezielter XML-Bearbeitung aus der Gesamtstrombezug-
   Gleichung entfernt (genau der von Kommentar id=65 markierte Term). Die
   κ-Vorwärmgleichung aus der vorherigen Runde war bereits korrekt entfernt.
   Kein `kappa`/`P_EF` mehr im Dokument (verifiziert).
4. **71 Word-Kommentare mit Ankertext ausgewertet und priorisiert bearbeitet:**
   - **Eigener Fehler gefunden und behoben:** meine vorherige Bearbeitung
     hatte an der StromNEV-Tarifpaar-Stelle ein doppeltes "als" erzeugt
     ("wird als als tariff_ambiguous") — korrigiert.
   - id=111 "Kreislauf" → "Rückkopplung" (konsistente Terminologie).
   - id=112 "LP statt MILP ohne Binärvariablen" auf Felix' ausdrücklichen
     Wunsch ("raus damit") aus den Limitations gestrichen.
   - id=32 "Was ist ein Tarifpaar?" — Tab. 1 direkt an der Stelle ergänzt
     ("Leistungs-+Arbeitspreis-Paar je Benutzungsdauer-Schwelle").
   - id=101 "CO₂-Preis, wo kommt er her?" — Referenzwerte (60 EUR/t CO₂,
     38 EUR/MWh_Hu Gas) mit Quelle direkt im Break-even-Satz ergänzt.
   - Reine Verständnis-/Scherzkommentare ohne Handlungsbedarf (ca. 20,
     z. B. id=8,19,22,25,26,43,47,58) sowie rein zustimmende Kommentare
     (id=114) nicht weiter bearbeitet.
   - **Nicht bearbeitet, da substanzielle inhaltliche Einordnung nötig
     (nicht eigenmächtig ergänzt):** id=97 (warum ist Metall der einzige
     Standort, bei dem AgNes die Kosten senkt?), id=108 (beantwortet die
     Diskussion die Kernfrage "wird Elektrifizierung durch AgNes
     wirtschaftlicher?" explizit genug?), id=90 (Vertraulichkeit der
     Standort-Rohdaten in Tab. 2), id=92 (bereits durch Punkt 2 oben gelöst).
     Mehrere weitere reine Formel-Verständnisfragen (id=39–47, 58, 72, 104–106)
     betreffen eingebettete Gleichungsobjekte, die ohne Risiko für die
     Dokumentintegrität nur punktuell (wie κ/P_EF oben) bearbeitbar sind,
     nicht pauschal — hierfür wäre eine gezielte Einzelfreigabe pro
     Gleichung sinnvoll.

## G. Verbleibende offene Punkte jetzt bearbeitet

**Neuer DOCX-Hash:** `bc2f856f341333f7c5d2c2d186a603354703a0db357c8b51b0dbc105f95c70b0`

1. **id=108 (zentrale Forschungsfrage):** §6 Diskussion beginnt jetzt explizit mit
   "Die zentrale Frage, ob AgNes die Elektrifizierung industrieller Prozesswärme
   wirtschaftlicher macht, lässt sich nicht pauschal beantworten: …" — macht die
   Frage sichtbar, bevor die standortabhängige Antwort folgt.

2. **id=97 (warum ist Metall der Ausreißer?):** direkt an derselben Stelle mit
   Zahlen aus den Kerndaten beantwortet — Metall bucht unter AgNes nur 15 %
   seiner Spitzenlast und bezieht 55 % seiner Energie oberhalb der Kapazität
   (`E₂/E`, `kpi_s1_s4.parquet`), profitiert also am stärksten davon, dass AgNes
   den Leistungsaufschlag bei geringer Nutzung im Gegensatz zu StromNEV auf
   `AP₂−AP₁` begrenzt (Tab. 1, Zeile "Max. Leistungsaufschlag bei geringer
   Nutzung"). Ergänzt außerdem die Rückfrage zu DAM/Peak-Entlastung: der
   Interaktionsterm wechselt standortspezifisch das Vorzeichen, ein
   allgemeiner Zusammenhang lässt sich aus vier Fällen nicht ableiten.

3. **id=90 (Vertraulichkeit Tab. 2):** Satz an die Tab.-2-Bildunterschrift
   angefügt, der explizit macht, was ohnehin bereits Praxis war: Standorte sind
   auf Branche+Region anonymisiert (keine Firmennamen), veröffentlicht werden
   nur die gezeigten Jahreskennzahlen, nicht die Lastgang-Zeitreihen (Verweis
   auf Data-Availability). **Keine Daten entfernt** — das ist keine Entscheidung,
   die ich für Sie treffen kann; falls die aggregierten Kennzahlen selbst
   (nicht nur die Zeitreihen) als vertraulich gelten sollen, bitte kurz
   bestätigen, dann kürze ich Tab. 2 entsprechend.

## H. Vollständige Konsistenzprüfung (auf explizite Nachfrage "ist alles aktuell?")

**Neuer DOCX-Hash:** `e4a5d494e3c17ca4f228239cc6cc7853ec1c488c3b66ebc5bd6813ea7f7daec9`

Systematisch neu geprüft statt nur auf vorherige Aussagen verlassen — dabei
**3 echte Lücken gefunden und behoben**:

1. **KRITISCH — `config.yaml` war nach meiner eigenen vorherigen Bearbeitung
   syntaktisch ungültig.** Beim Definieren des `alpha`-Kommentars hatte ich
   einen mehrzeiligen String im Python-Stil (adjazente Anführungszeichen)
   geschrieben — das ist kein gültiges YAML und hätte **jeden künftigen
   Lauf beim Config-Laden zum Absturz gebracht** (`yaml.parser.ParserError`).
   Erst durch den jetzigen End-to-End-Check (`AGNES_DRY_RUN=1`) aufgefallen.
   Behoben (ein zusammenhängender String); YAML lädt jetzt wieder korrekt,
   Dry-Run läuft ohne Fehler durch T01–T11b.
2. **Abb. 4 (Break-even) hatte einen alten, in der Abbildung selbst
   eingebrannten Titel.** Die Korrektur "ELEC vs. GAS" → "Hybrid-ELEC vs.
   GAS" aus einer früheren Runde hatte nur den DOCX-Bildunterschriftentext
   erreicht, nicht den Matplotlib-`suptitle`-String im Plot-Code selbst —
   Bild und Unterschrift widersprachen sich. `agnes_p2h.py` und
   `regenerate_figures.py` korrigiert, Abb. 2–4 aus den bereits validierten
   Lauf-Daten neu gebaut (keine Zahlenänderung, nur Titel) und alle drei neu
   eingebettet.
3. **Die falsche Rechtsgrundlage "StromNEV § 19 Abs. 2" stand noch an einer
   zweiten, unabhängigen Code-Stelle** (`agnes_p2h.py`, Tabelle-1-Generierung,
   nicht über `config.yaml` gespeist) — die DOCX-Tabellenzelle hatte ich
   bereits von Hand korrigiert, der Code, der `table01_regulatory.csv/.md`
   erzeugt, aber nicht. Jetzt auf `§ 17` korrigiert; die bereits exportierten
   `table01_regulatory.csv/.md` (im Lauf-Ordner und in `submission_pack/`)
   direkt nachgezogen.

**Zusätzlich verifiziert (alles bestätigt korrekt, keine Änderung nötig):**
- Alle 3 eingebetteten Diagramme (Abb. 2–4) visuell inhaltlich gegen die
  aktuellen Lauf-Daten geprüft — Bild-Hashes wichen zwar von den
  Rohdateien in `outputs/` ab (Word komprimiert Bilder beim Speichern neu),
  der **Inhalt** stimmt aber exakt überein.
- Tab. 3 (Kern-KPI): alle 32 Zellenwerte 1:1 gegen `table03_core_results.md`
  verglichen — exakte Übereinstimmung.
- Interaktionsterm-, Break-even-, Speicherwert- und θ-Sätze erneut gegen
  `interaction.csv`/`breakeven.csv`/die normierten Speicherwerte/
  `supplement_s5_alpha_f.csv` geprüft — konsistent.
- Volltextsuche nach alle bekannten Alt-Werten (30,4–52,9; 31,5 %;
  35,24 etc.; "Hochtemperatur-Wärmepumpe"; "kappa"; "P_EF"; alte
  §19-Abs.2-Zitate; "genuin, bereits 15-min") — keine Treffer mehr.
- `agnes_p2h.ipynb` aus dem finalen `agnes_p2h.py` neu synchronisiert.
- `submission_pack/` komplett neu synchronisiert (58 Dateien,
  `sha256sum -c` grün).

**Einzige verbliebene, nicht behebbare Diskrepanz:** Bild-Byte-Hashes von
Abb. 2–4 unterscheiden sich zwischen `outputs/.../figures/*.png` und den in
der DOCX eingebetteten Kopien, weil Microsoft Word Bilder beim Speichern neu
komprimiert. Das ist normales Word-Verhalten, keine inhaltliche Abweichung
(visuell verifiziert) — bei jedem künftigen "Speichern unter" in Word wird
sich der Bild-Hash erneut ändern, ohne dass sich der Inhalt ändert.

## E. Umfangsprüfung

Dokument bleibt bei 154 Absätzen / 3 Tabellen / 4 Abbildungen, keine Strukturänderung — Umfang unverändert im Rahmen der ca. 8 Seiten.
