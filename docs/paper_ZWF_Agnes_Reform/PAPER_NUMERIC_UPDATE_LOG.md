# PAPER_NUMERIC_UPDATE_LOG.md

**Datei:** `20260922_Bestellkapazitaet_ZWF_lkr.docx`
**Quelle aller neuen Zahlen:** `outputs/20260922T203807/` (gültiger, per `FINAL_QA_SUMMARY.md` abgenommener Lauf)
**Alte Zahlenbasis:** unbekannter Vorlauf vor dem ETA_GB-Fix (nicht mehr im Repo referenzierbar; die im Draft vorgefundenen Werte wurden 1:1 als "alt" dokumentiert, ohne Herkunftsnachweis, da sie vor Beginn dieser Session in die Datei geschrieben wurden)
**Hash vor Änderung:** `9d6aee2df02208c45ee9c4693c17fbcf02175a04a45b2f970b56bff5faff0803`
**Hash nach Änderung:** `4acacdffc77cde9ea164ac66e5345c9dcc5513c929a1bd58c06e316fcb326f8f`
**Methode:** `python-docx`, Ersetzung ausschließlich innerhalb bestehender Text-Runs (keine Neuerzeugung von Absätzen/Runs), damit eingebettete Formel-/Symbolobjekte unangetastet bleiben. Alle 42 Absatz-Ersetzungen + 1 Nachkorrektur + 32 Tabellenzell-Ersetzungen wurden vor dem Speichern gegen den tatsächlich vorgefundenen Text verifiziert (Fail-Fast: jede nicht gefundene Zielzeichenkette hätte das Speichern verhindert).

## A. Reine Zahlenkorrekturen (Marker-Herkunft eindeutig)

| # | Fundstelle | Alt | Neu | Marker/Quelle |
|---|---|---|---|---|
| 1 | Kurzfassung (P8), Summary (P10) | LCOH_inc 30,4–52,9 / 30.4–52.9 EUR/MWh | 30,7–58,5 / 30.7–58.5 EUR/MWh | R-ABS-01 |
| 2 | Kurzfassung, Summary | Δ Fixpreis −0,3 bis +14,2 | −4,1 bis +14,9 | R-NET-FIX-MIN/MAX |
| 3 | Kurzfassung, Summary | Δ Day-Ahead −4,1 bis +14,8 | −8,5 bis +15,1 | R-NET-DA-MIN/MAX |
| 4 | Kurzfassung, Summary, Kernaussage 3, Industrielle Anwendung, §5 (P73), §7 Fazit | 31,5 % Regelabweichung | 34,7 % | R-ABS-03 / R-RULE-DEV |
| 5 | §5 Ergebnisse (P67) | LCOH-Effekt 15min vs. 60min: 0,02 % / 0,05 % | 0,04 % / 0,11 % | R-TIME-02 |
| 6 | §5 Ergebnisse (P68) | Δ Fixpreis/Day-Ahead (Wiederholung) | s. Zeile 2/3 | R-NET-* |
| 7 | §5 Ergebnisse (P68) | Interaktionsterm −3,8 bis +4,6 EUR/MWh | −4,4 bis +4,8 EUR/MWh | R-INT-MIN/MAX |
| 8 | §5 Ergebnisse (P70) | ΔHP-Kapazität −3.443 bis +10 kW | −4.850 bis +38 kW | R-DES-HP |
| 9 | §5 Ergebnisse (P70) | ΔTES-Kapazität −10.816 bis +11 kWh | −14.671 bis +1.380 kWh | R-TES-MIN/MAX |
| 10 | §5 Ergebnisse (P70) | TES-Systemwert 236.109 EUR/a | 361.848 EUR/a | R-TES-VALUE |
| 11 | §5 Ergebnisse (P73) | C/Pmax-Spanne 15–92 % | 15–91 % | R-BOOK-MIN/MAX |
| 12 | §5 Ergebnisse (P76) | Break-even-Gaspreis 16–32 EUR/MWh_Hu | 13–32 EUR/MWh_Hu (+ Konvergenzhinweis 7/8) | R-BE-GAS |
| 13 | §5 Ergebnisse (P76) | Break-even-CO₂-Preis 18–31 EUR/t | 11–30 EUR/t (+ Konvergenzhinweis 2/8) | R-BE-CO2 |
| 14 | §5 Ergebnisse (P78) | Sensitivität ΔC 62.665 kW | 63.456 kW | R-SENS-C |
| 15 | §5 Ergebnisse (P78) | Sensitivität ΔTES 29.286 kWh | 37.895 kWh | R-SENS-TES |
| 16 | Tab. 3 (KPI-Tabelle), alle 4 Standortzeilen × 8 Spalten (32 Zellen) | siehe DOCX-Tabelle vor Änderung | siehe DOCX-Tabelle nach Änderung | `table03_core_results` / `lcoh_inc.csv` |

## B. Inhaltliche Korrektur mit Konsequenz für die Kernaussage (bitte gesondert prüfen)

**Interaktionsterm-Richtung (Kernaussage 4, §5 P68, Fazit P91):**
Alt: *"an drei von vier Standorten positiv … überwiegend komplementär"*
Neu: *"an 2 von 4 Standorten negativ, an 2 von 4 positiv … uneinheitlich, in der Summe leicht substitutiv"*

Grund: `interaction.csv` im neuen Lauf zeigt food=+0,158, chemistry=+4,763, metal=−4,384, paper=−0,050 EUR/MWh — ein exaktes 2:2-Patt, nicht 3:1 wie zuvor. Die Pipeline selbst klassifiziert dies über `R-INT-01` als **"substitutiv"**, weil ihre Tie-Break-Regel (`n_neg >= n_pos` bei Gleichstand) einen 2:2-Patt der negativen Seite zuschlägt. Der DOCX-Text wurde bewusst **nicht** strikt "substitutiv" geschrieben, sondern neutral als 2:2-Patt mit "in der Summe leicht substitutiv" (Summe der vier Δinter-Werte ≈ +0,49 EUR/MWh, also technisch knapp positiv, aber die Standortzahl ist exakt geteilt) — das ist die ehrlichste Formulierung, die sowohl dem Pipeline-Label als auch den Rohzahlen gerecht wird.

**Dies ist die einzige Änderung in diesem Update, die eine Kernaussage des Papers dem Sinn nach verschiebt (nicht nur eine Dezimalstelle).** Bitte vor Einreichung nochmals persönlich gegenlesen.

## C. Methodische Textkorrekturen (kein Zahlenbezug)

| # | Fundstelle | Korrektur |
|---|---|---|
| 1 | §4 Modell (P56), §4 (P61), §5 (P67), §6 Diskussion (P82) | "15-min-Auflösung" als Kernmodell → korrigiert zu "stündliche Auflösung" als Kernmodell, 15-min nur als Validierungssubset (Chemie, Papier); "replizierte Stundenpreise" als generelle Limitation → auf den 15-min-Validierungsfall verengt |
| 2 | §4 Modell (P55) | Zwei-Band-Struktur (Niedertemperatur ≤100 °C + Hochtemperatur 100–250 °C) → korrigiert zu einem einzelnen generischen Prozesswärmeband je Standort |
| 3 | Schlüsselwörter (P11) | "Hochtemperatur-Wärmepumpe" → "industrielle Wärmepumpe, Power-to-Heat" |
| 4 | §4 Modell (P57) | Ergänzt: explizite Klarstellung, dass die Gaskessel-Variable Nutzwärme abbildet und der Brennstoffbedarf durch Division durch η_GB=0,9 berechnet wird (ETA_GB-Bugfix-Konsequenz) |
| 5 | Kernaussage 3 (P15), §5 (P73), §7 Fazit (P91) | Regelvalidierung: exakte Nutzer-Wortwahl aus R-CONCLUSION-02 sinngemäß übernommen; V-04 (KKT-Konsistenzcheck auf realisiertem LP-Lastgang) explizit als ergänzender Implementierungs-Validierungstest genannt, nicht als Ersatz für R-RULE-DEV |
| 6 | §1 Einleitung (P23), Tab.-Beschriftungen (P30, P64, P79) | Dangling-Referenz "Tabelle 1" (keine solche Tabelle existiert im Dokument) entfernt/umformuliert; Tabellennummerierung durchgängig korrigiert: Tab. 2→1 (Regimevergleich), Tab. 3→2 (Standortübersicht), Tab. 4→3 (Kern-KPI); dangling Querverweis "(vgl. 4.2/8.4)" (Abschnitt 8 existiert nicht) entfernt, durch "(s. Abschn. 6, Einschränkungen)" ersetzt |

## D. Geprüft, keine Änderung nötig

- **AgNes-Framing als "parametrisierte/stilisierte Szenarioanalyse":** Draft verwendet bereits durchgängig "Szenarioannahmen" / "nicht als Prognose" (P26, P27) — inhaltlich bereits konform, keine Änderung vorgenommen.
- **S10/Rolling-Horizon-Beschreibung:** Im aktuellen Draft existiert **keine** Textstelle, die S10 beschreibt oder darauf verweist (kein §7.4, keine Rolling-Horizon-Erwähnung im Fließtext). Die vom Nutzer geforderte restriktive Formulierung ("energiepreisbasierte Rolling-Horizon-Dispatch-Analyse bei fixierter Auslegung …") konnte daher **nicht angewendet** werden, weil es nichts zu korrigieren gab. Die validierten V-03-Daten (`rolling_horizon.csv`, s. `FINAL_RESULT_TRACEABILITY.csv`) stehen bereit, falls der Autor eine eigene §7.4 ergänzen möchte — dies wurde bewusst **nicht** automatisch als neuer Abschnitt eingefügt, um keine unangeforderten Inhalte zu erzeugen.
- **R-01 (θ-Faktor 8,75), R-VAL-01 (Intervallzahlen), Tab. 2/Standortübersicht (Wärmebedarf/Peak/Volllast-h), Tab. 1/Regulatorik:** unverändert, da unabhängig vom ETA_GB-Fix (Rohdaten bzw. statische Regulatorik).

## F. Korrekturrunde 2 (2026-09-22, nach Autoren-Feedback zum Interaktionsterm)

**Hash vor Runde 2:** `4acacdffc77cde9ea164ac66e5345c9dcc5513c929a1bd58c06e316fcb326f8f`
**Hash nach Runde 2:** `bfcec7f8daf58fd8538263d7a4ac8e7a1067f23a8c850f9790e144f8960e6209`

Der Autor bewertete die Formulierung "in der Summe leicht substitutiv" aus Runde 1
zu Recht als zu stark: Ein exaktes 2:2-Patt (food/chemistry positiv,
metal/paper negativ) erlaubt keine robuste Richtungsaussage. Übernommen wurde
die vom Autor vorgeschlagene, wissenschaftlich sauberere Formulierung — "der
Interaktionsterm ist standortspezifisch uneinheitlich … keine robuste
allgemeine Komplementaritäts- oder Substitutionsaussage ableitbar" — an drei
Stellen: Kernaussage 4 (P16), §5 Ergebnisse (P68), §7 Fazit (P91).

**Geprüft und bewusst NICHT übernommen:** Der Autor bot optional eine
Alternativformulierung an ("Im ungewichteten Mittel ist der Interaktionsterm
leicht negativ …"). Nachrechnung aus `interaction.csv` (neuer Lauf):

```
food:       +0,158044
chemistry:  +4,763046
metal:      −4,383664
paper:      −0,049972
Summe:      +0,487454
Mittel:     +0,121863 EUR/MWh   (POSITIV, nicht negativ)
```

Der ungewichtete Mittelwert ist leicht **positiv** (+0,12 EUR/MWh), nicht
negativ. Die optionale Alternativformulierung des Autors wurde daher **nicht**
verwendet, da sie dem tatsächlichen Rechenergebnis widerspricht — konsistent
mit der wiederholten Vorgabe, keine Behauptung ungeprüft zu übernehmen (auch
nicht aus Autoren-Feedback). Die verwendete Hauptformulierung nennt bewusst
keinen Mittelwert und ist damit unabhängig von diesem Rechenfehler korrekt.

**Zusätzlich im Quellcode korrigiert (`agnes_p2h.py`, R-INT-01-Marker,
Zeile ~2388):** Die bisherige Klassifikationslogik nutzte `n_neg >= n_pos` und
etikettierte einen exakten Patt automatisch als "substitutiv" — ein
Tie-Break-Artefakt, keine inhaltliche Aussage. Ersetzt durch eine echte
Mehrheitsprüfung (`>` statt `>=`) mit einer dritten Kategorie "uneinheitlich"
für den Patt-Fall; die generierte `display_value` benennt dann explizit
Anzahl negativ/positiv und den Hinweis "keine robuste allgemeine
Richtungsaussage ableitbar". Notebook aus dem korrigierten Skript neu
synchronisiert (`jupytext --to notebook agnes_p2h.py -o agnes_p2h.ipynb`);
Validierung via `AGNES_DRY_RUN=1` durchgeführt (Ergebnis s. Abschlussbericht).
Diese Code-Änderung wirkt sich **nicht** auf die bereits berechneten
Zahlenwerte in `outputs/20260922T203807/` aus (nur auf die Textlabel-Logik für
künftige Läufe) — der angenommene Lauf bleibt gültig, siehe
`FINAL_QA_SUMMARY.md`.

## G. Korrekturrunde 3 (2026-09-23, Abbildungen)

**Hash vor Runde 3:** `bfcec7f8daf58fd8538263d7a4ac8e7a1067f23a8c850f9790e144f8960e6209`
**Hash nach Runde 3:** `54ca222f1a449caec88e7b30f4a016b973e0c8853879da7db8f4003ef9d82fa2`

Auf die Nutzerfrage "ist das Word mit neuen Zahlen, Abbildungen, Tabellen,
Ergebnissen etc. aktuell?" wurde erstmals geprüft, ob die **eingebetteten
Bilder** (nicht nur der Fließtext) aktuell sind — bislang wurden in dieser
Session ausschließlich Absatztexte über `python-docx` bearbeitet, nie die
`word/media/*`-Bildinhalte selbst.

**Befund 1 — eingebettete Abbildungen waren veraltet.** Keines der 4
eingebetteten Bilder (Abb.1–4) stimmte per SHA-256 mit den Abbildungen aus
dem alten (`20260915T195641`) oder dem neuen, validierten Lauf
(`20260922T203807`) überein. Visuell bestätigt am Beispiel Abb.2
(Kernergebnisse): alte eingebettete Speicherkapazität Papierfabrik ≈19 MWh
vs. tatsächlich berechnet ≈29 MWh.

**Befund 2 — Abbildungsnummerierung war strukturell inkonsistent,
unabhängig von der Aktualität.** Die in `agnes_p2h.py`/`regenerate_figures.py`
erzeugten Diagramme bebildern sich selbst mit "Abb. 3/4/5" (5er-Schema inkl.
Analytik-Abbildung als "Abb. 2"), während die DOCX-Bildunterschriften bereits
ein 4er-Schema ohne Analytik-Abbildung verwenden ("Abb. 2" = Kernergebnisse
usw.). Dieser Versatz bestand unabhängig vom ETA_GB-Fix bereits vorher.

**Nutzerentscheidung:** 4 Abbildungen (Analytik-/Sensitivitätsabbildung
bleibt außerhalb des Haupttextes).

**Durchgeführt:**
1. `agnes_p2h.py` + `regenerate_figures.py`: Diagrammtitel korrigiert —
   `fig03_core_results`→"Abb. 2", `fig04_load_duration`→"Abb. 3",
   `fig05_breakeven`→"Abb. 4"; `fig02_analytics` umbenannt zu
   "Zusatzabbildung: … (nicht Teil der Haupttext-Abbildungen)" ohne
   Abbildungsnummer, um Verwechslung mit der echten Abb.2 auszuschließen.
2. Notebook aus dem korrigierten Skript neu synchronisiert.
3. Abb.2–4 (`fig03_core_results`, `fig04_load_duration`, `fig05_breakeven`)
   mit `regenerate_figures.py 20260922T203807` neu aus den bereits
   validierten Lauf-Daten gebaut (kein Re-Solve nötig) — jetzt korrekt
   betitelt UND mit den aktuellen Zahlen.
4. In der DOCX per `python-docx` die Bild-Bytes der 3 betroffenen
   `InlineShape`s direkt ersetzt (Position/Anzeigegröße unverändert
   beibehalten; altes und neues Seitenverhältnis je Abbildung nahezu
   identisch, s. u. — keine relevante zusätzliche Verzerrung).
5. Per SHA-256 verifiziert, dass die eingebetteten Bild-Bytes exakt den
   neu erzeugten Dateien entsprechen.

**Bewusst NICHT ersetzt: Abb. 1 (Systemgrenze/Superstruktur).** Das
eingebettete Bild ist eine sauber gezeichnete Vektorgrafik und zeigte auch
vorher schon nur EIN generisches Prozesswärme-Ausgangsfeld (kein LT/HT-Split)
— inhaltlich also nicht falsch, nur weniger explizit als der aktuelle
Pipeline-Output. Die automatisch generierte `fig01_superstructure.png` des
aktuellen Laufs hat zudem einen sichtbaren Text-Überlappungs-Rendering-Fehler
("Wärmepumpe (COP)" überlappt mit der Formel). Ein Austausch hätte die
Bildqualität verschlechtert, ohne einen Sachfehler zu beheben — daher
beibehalten. Empfehlung: `fig01_superstructure()`-Plotcode
(Textpositionierung) bei Gelegenheit fixen, unabhängig von diesem Review.

**Seitenverhältnis-Kontrolle (alt vs. neu, zur Beurteilung der
Verzerrung):**

| Abbildung | Anzeige-Seitenverhältnis (DOCX, unverändert) | altes Bild-Seitenverhältnis | neues Bild-Seitenverhältnis |
|---|---|---|---|
| Abb. 2 (core_results) | 3,353 | 2,860 | 2,862 |
| Abb. 3 (load_duration) | 1,220 | 1,140 | 1,140 |
| Abb. 4 (breakeven) | 3,104 | 2,335 | 2,336 |

Die Anzeigebox war schon vor diesem Fix nicht exakt bildproportional (vom
Autor vermutlich manuell in Word skaliert); da altes und neues Bild nahezu
identische Eigen-Seitenverhältnisse haben, ändert der Austausch den Grad der
Verzerrung nicht.

## E. Nicht in den DOCX übernommen (verfügbar, aber ungenutzt)

Folgende validierte, "belegte" Marker haben aktuell **keine** korrespondierende Textstelle im Draft und wurden daher nicht eingefügt (kein Erfinden neuer Abschnitte): `R-DEC-MECH`, `R-DEC-DISP`, `R-DEC-DESIGN` (Dekompositions-Mechanik), `R-TES-CASE`, `BIB-01`, `BIB-03`. Vollständig in `FINAL_RESULT_TRACEABILITY.csv` dokumentiert.
