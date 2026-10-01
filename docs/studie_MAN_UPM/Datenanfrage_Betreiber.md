# Datenanfrage an den Netzbetreiber – Studie Großwärmespeicher MAN/UPM (Stadtbach)

Stand: 2026-10-01 · Bezug: Notebook `studie_grosswaermespeicher_MAN_UPM.ipynb`, Kapitel 23 (Datenlücken) und 23.1 (Plan)

**Zweck.** Die hydraulisch-thermische Studie wurde ausschließlich mit den vorhandenen Messdaten (ACRON 2025, Stundenwerte), den Plänen WV640/WV650/WV660 und der Topologie-Vorlage `Stadtbach_topo.yaml` gerechnet. Wo Informationen fehlen, wurden **gekennzeichnete Annahmen** getroffen. Diese Liste nennt die Informationen, die die Annahmen durch belastbare Werte ersetzen und die Ergebnisse (insbesondere die Maßnahmenrangfolge) absichern.

**Wie lesen.** *Priorität 1* = ändert die Rangfolge der Maßnahmen oder die Machbarkeit; *Priorität 2* = ändert Zahlenwerte spürbar; *Priorität 3* = Absicherung/Feinschliff. Die Spalte „Heutige Annahme“ zeigt, womit die Studie derzeit rechnet – bitte korrigieren, falls falsch (auch eine Korrektur ohne neue Daten hilft).

---

## A. Erzeuger, Pumpen, Druckhaltung

| Nr. | Prio | Angefragte Information | Warum wichtig (Einfluss auf die Studie) | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| A1 | 1 | **Pumpenkennlinien** (Förderhöhe über Volumenstrom, Wirkungsgrad, Drehzahlbereich, Bypass) der Umwälzpumpen HKW, AVA, GT-Ost, BMHKW, Heizwerk Süd sowie Pumpstationen PSS und PSW | Entscheidet, wie weit die **Erzeugerdrücke angehoben** werden können – in der Studie die wirksamste Einzelmaßnahme (Bedarf ≈ 0,5 bar heute, ≈ 1,1 bar bei +20 % Last) | Erzeugerdrücke als feste Randbedingung auf dem Niveau 2025; keine Kennlinien; PSS/PSW nur mit gemessenem Druckgewinn | Kennlinienblätter oder Tabellen (V̇, H, η); Typenschilder |
| A2 | 1 | **Abschalt-/Grenzdrücke und max. zulässige Betriebsdrücke** je Netzbereich und Station; Ansprechdrücke Sicherheitsventile; Bestätigung der **PN-Zonen** (Verbund PN25, Westnetz PN16 über Wärmeübertrager getrennt) | Obergrenze der Druckanhebung und des Speicher-Auslegungsdrucks (derzeit ≈ 17 bar Ü am MAN abgeleitet) | WV640 Bl. 3: Ruhedruck HKW 8,4 bar Ü, Δp intern 0,8–1,3 bar; PN25/PN16 aus Plänen | Auszug Betriebsanweisung / Anlagenschema |
| A3 | 1 | **Regelphilosophie der Erzeugerstationen**: Δp-Sollwerte, Druckhaltung, Schleppzeiger, Regelbereich, wie reagieren AVA/GT/BM bei Lastzunahme | Ost-Bereich ist das größte Modellrisiko (±1 bar); die Erzeuger regeln dort Differenzdruck, im Modell nur über zwei effektive Offsets abgebildet | AVA und HKW als Druckränder; Offsets kalibriert | Schemata, Sollwerttabellen, Reglerbeschreibung |
| A4 | 2 | **Leistungs- und Temperaturgrenzen der Erzeuger** (MW, kg/s, min./max. Vor- und Rücklauftemperatur, Verfügbarkeit, Elektrodenkessel/Kessel: Standort, Leistung, Regelung) | Erzeugerlimit (HKW-Durchfluss) begrenzt ab ≈ +15 % Ausbau; Wärme-Szenarien GT-/AVA-Ausfall | Limit = in 2025 beobachtetes Maximum (P99,9) je Erzeuger | Tabelle je Erzeuger |
| A5 | 3 | Soll-Vorlauftemperatur im Betrieb: tatsächliche **Heizkurve/Fahrweise** unter −10 °C (Vorgabe: lineare Kurve 120 °C @ −10 … 90 °C @ +20) | Vorlauftemperatur bestimmt Massenstrom bei gleicher Wärme | Lineare Kurve als Hauptannahme; YAML-Kurve (122 → 70 °C) als Alternative | Beschreibung/Tabelle |

## B. Netz, Topologie, Schaltzustände, Höhen

| Nr. | Prio | Angefragte Information | Warum wichtig | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| B1 | 1 | **Schaltzustände 2025** (Stellung der Armaturen, insbesondere 001.2, 342.1, 342.3, 338.x, 818.x, 773.x) als Protokoll/Zeitreihe; **Betriebsanweisung** für getrennten Betrieb (WV650/660) | Ob MAN bei Trennung an der HKW- oder Ost-Seite liegt, entscheidet, ob der Speicher bei Trennung überhaupt wirkt (342.3: ja, 342.1: nein) | S7-1 (Trennung 342.3) und S7-2 (342.1) beide gerechnet; Landungen SL6/SL7 offen | Schaltprotokolle, Betriebsanweisung |
| B2 | 1 | Bestätigung der **Transportgrenzen** SL5/SL6/SL7 im getrennten Betrieb (750/500/300 t/h) und der Mindest-Ruhedrücke je Bereich | Bewertung getrennter Betriebszustände | WV650-Angabe laut Auftrag, noch nicht am Plan geprüft | Bestätigung / aktueller Stand |
| B3 | 2 | **Leitungsdaten** der Hauptleitungen (Nennweite, Länge, Material, Baujahr, Rauheit, Dämmserie) als **GIS-Export** (Shape/DXF/GeoJSON), insbesondere SL2, SL3, SL4, Verbundleitungen und SL5–SL7 | Rohrlängen stammen teils aus Rasterplänen (±7 %), teils aus Schätzung; Verbundkanten (M12, M23, M24, M34) sind aggregiert | Längen aus Plan-Bildanalyse (Maßstab 1:10 000), Schätzwerte für Verbund, Rauheit 0,1 mm | GIS-Daten oder Leitungsliste |
| B4 | 2 | **Geländehöhen** der Stationen, Armaturen und Erzeuger (DGM oder Vermessung), Hoch-/Tiefpunkte im Netz | Absolute Drücke; Siede-/Mindestdruck an Hochpunkten | Höhen aus Schwachlast-Differenzdrücken abgeleitet (±3–5 m ≙ ±0,3–0,5 bar) | Höhenliste je Knoten/Station |
| B5 | 2 | **Stichleitungen und Sonderbereiche** (z. B. Beethovenpark: ca. 2,9 km DN150), Verbindungen 141.1/187.1 (Plan-Widersprüche) | Nicht abbildbare Stichleitungsenden; Konnektivität | Stichleitungen nicht modelliert | Planauszug/Bestätigung |
| B6 | 3 | **Westnetz**: Primärseite/Wärmeübertrager (Leistungen, Δp, Regelung) | Westnetz derzeit nur als Entnahme am Knoten HWW | Westnetz PN16, hydraulisch entkoppelt (Partialkorrelation ≈ 0 bestätigt) | Datenblätter |

## C. Speicher (MAN/UPM und Alternativen)

| Nr. | Prio | Angefragte Information | Warum wichtig | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| C1 | 1 | **Standort/Fläche**: konkreter Anschlusspunkt (Armatur 342.x?), Höhenlage, verfügbare Fläche und Bauhöhe, Genehmigungslage; **Alternativstandorte** (Innenstadt/West, Süd) | Der Standort ist der größte Hebel des Speichers (Innenstadt −64 % Δp-Defizit vs. MAN −42 %); Machbarkeit unbekannt | MAN-Knoten aus WV650 angenommen; Innenstadt = Sektionsknoten (Gebiet, kein Punkt) | Lageplan, Machbarkeitsnotiz |
| C2 | 1 | **Technisches Konzept**: Druckspeicher (Höhe/Durchmesser, Auslegungsdruck/-temperatur, Druckhaltung/Inertisierung, Dämmung), Anschlussleitungen (DN, Länge, Armaturen, Regelventile), Pumpenkonzept (reversibel/getrennt), Zielleistungen | Förderhöhe (bis ≈ 4 bar bei 40 MW am MAN), Anschlussverluste, Auslegungsdruck | 5 000 m³ (YAML), 20 m Höhe, DN300, 250 m je Strang, 40 MW, Pumpen-η 0,75 | Konzeptpapier/Projektunterlagen |
| C3 | 1 | **Projektwerte und Kosten**: Volumen, Leistungen, Temperaturbereich, Investitions- und Betriebskosten, Zeitplan | Kosten-Nutzen-Vergleich (Paket C2 des Plans) ist ohne Kosten nicht möglich | Nur hydraulische Rangfolge | Kostenschätzung, Angebote |
| C4 | 2 | Soll-**Betriebsstrategie**: Lade-/Entladezeiten, Prognosegrundlagen, Füllstandsführung, zulässige Temperaturen | Regelstrategie und nutzbare Kapazität | Optimierte Fahrweise je Tag (Stufen: Druck → Last → Spitze → Pumpstrom) | Beschreibung |

## D. Last, Kunden, Ausbau

| Nr. | Prio | Angefragte Information | Warum wichtig | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| D1 | 1 | **Ausbauvorhaben** (Ort/Straße oder Anschlussknoten, Leistung, Zeitplan, Temperaturanforderung) | Wo der Ausbau stattfindet, entscheidet über die Engpässe (+10 % in Süd ≈ 87 bar·h Defizit, in Ost ≈ 27 bar·h) | Proportionaler Zuwachs +10…50 % sowie +30 % nur Ost | Liste/GIS |
| D2 | 2 | **Lastgänge/Zählerdaten je Sektion bzw. Station** (stündlich; Anschlusswerte), Kunden-**Mindestdifferenzdruck** (Vertrag/Auslegung), Rücklauftemperatur-Anforderungen | Lastanteile je Sektion sind nicht identifizierbar (nur 7 Stationen gemessen); Δp-Grenzwert ist Annahme | Lastanteile kalibriert (Prior: Anschlussleistung), Kunden-Δp ≥ 1,0 bar | Zeitreihen (CSV/Parquet), Verträge/Auslegungswerte |
| D3 | 2 | **Auslegungslast** (Außentemperatur −14 °C?) und Gesamt-Lastgang mehrerer kalter Winter (Definition: was enthält der Lastgang 2020–2022?) | Lastextrapolation unsicher (±25 %) | Basistag 14.02.2025 (≈ 215 MW Tagesmittel) als Auslegungsniveau; Lastgang-Extrapolation 216/269 MW | Lastgangdateien + Definition |

## E. Messdaten und Messstellen

| Nr. | Prio | Angefragte Information | Warum wichtig | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| E1 | 2 | **Bestätigung der Messdefinitionen**: Druck = Überdruck (bar); Durchfluss in m³/h; Zeitstempel (lokal, Sommerzeitumstellung); Messort und Sensorhöhe je Messstelle; Messunsicherheiten | Einheiten/Höhenbezug wurden aus Plausibilität abgeleitet (bestätigt durch Bilanzen, aber nicht vom Betreiber) | Überdruck, m³/h, lokale Zeit | Kurzbestätigung / Messstellenliste |
| E2 | 1 | **Zusatzmessungen/Feinauflösung**: Kunden-Δp (Stunden-Minimum/-Maximum oder Minutenwerte) an SEC2 (Fuggerstr.), SEC4 (Theodor-Heuss-Platz), HWW, Lechhauser Str., Schlettererstr.; Druck an Armaturen 342.x; Durchflüsse an Koppelstellen (Übertragung zwischen SL1–SL4 und Ost); Pumpenleistung/-drehzahl PSS/PSW | Differenzdruck bei Hochlast ist die kritische Größe (Modell-RMSE ≈ 0,3–0,6 bar); Verbundflüsse sind aus Daten nicht bestimmbar | Stundenwerte 2025; Bias-Korrektur aus Hochlaststunden | Zeitreihen |
| E3 | 2 | **Ereignisprotokolle 2025** (Störungen, Druckeinbrüche, Wartung) | Im Datensatz gibt es 9 Einzelstunden mit Kunden-Δp < 0,8 bar (2× Nullwerte); unklar, ob Messfehler oder reale Ereignisse | Als Ausreißer behandelt | Ereignisliste mit Zeitpunkten |
| E4 | 3 | Messdaten **weiterer Jahre** (insbesondere kalte Winter) | Validierung bei Extremlast; 2025 war mild (kältester Tagesmittelwert −7,3 °C) | Nur 2025 | gleiches Format wie ACRON-Export |

## F. Wirtschaftlichkeit und Rahmen

| Nr. | Prio | Angefragte Information | Warum wichtig | Heutige Annahme | Gewünschtes Format |
|---|---|---|---|---|---|
| F1 | 1 | Kosten: Speicher, **Leitungsverstärkung** (€/m je DN), Erzeugerpumpen-Umrüstung, Regelung | Vergleich der drei Maßnahmenfamilien | keine | Kostenansätze |
| F2 | 2 | Strom-, Wärme- und Brennstoffpreise, Wärmegestehungskosten je Erzeuger, ggf. CO₂-Faktoren | Zielfunktion der Fahrweisenoptimierung | Pumpstrom 120 €/MWh (Platzhalter), sonst nur hydraulisch | Tabelle |

## G. Rückfragen zur Plausibilisierung (Ja/Nein genügt)

1. Gilt für den Verbund PN25 (Westnetz PN16)? Ist 14,5 bar Ü im Verbund (Maximum in den Rechnungen) zulässig?
2. Sind PSS/PSW im Normalbetrieb Bypass (Druckgewinn im Median 0 bar) und nur bei Spitzen aktiv?
3. Liegt MAN/UPM an der SL5 zwischen Koppelstelle 001.2 und SL5-Mitte (Armaturen 342.1/342.2/342.3)?
4. Ist ein Wärmeübertrager im MAN-Anschluss (Kundenstation) hydraulisch getrennt vom geplanten Speicheranschluss zu denken?
5. Sind die Werte „Mindest-Ruhedruck bei 120 °C“ (Mitte-City 6,5 / Mitte 3,2 / Süd 3,2 / Ost 2,5 bar Ü) aktuell?
6. Welche Kunden-Differenzdrücke gelten als „kritisch“ (Alarm/Beschwerdegrenze)?
7. Gibt es bekannte Engpässe oder Beschwerden im Winter 2025 (Ort, Zeit)?

---

*Hinweis zur Weitergabe:* Die Liste enthält keine Messdaten, aber einzelne aus den Daten abgeleitete Kennwerte (z. B. Bedarf an Druckanhebung, Defizite). Bitte vor externer Weitergabe prüfen, ob diese Kennwerte freigegeben sind.
