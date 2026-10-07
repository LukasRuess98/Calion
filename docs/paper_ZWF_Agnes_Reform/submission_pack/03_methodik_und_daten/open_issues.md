# open_issues.md

Automatisch erzeugt (§12), Run-ID `20260922T203807`.

## 0. Bugfix seit dem letzten Lauf (invalidiert alle vorherigen Zahlen)

**ETA_GB-Bug behoben:** `ETA_GB` (Gaskessel-Wirkungsgrad) war in config.yaml/
agnes_p2h.py definiert, wurde aber in keiner Gleichung verwendet. Gas- und
CO2-Kosten wurden direkt auf q_gb (Nutzwärme, kW_th) statt auf den
Brennstoffbedarf q_gb/ETA_GB berechnet - eine Unterschätzung um den Faktor
1/eta_GB (~11% bei eta=0,90). Betrifft: GAS-Konfiguration, optionalen
Gaskessel-Einsatz in ELEC, alle Break-even-Preise, LCOH_inc an allen
Standorten mit Gaskesselanteil. Alle Zahlen aus früheren Läufen sind damit
ungültig und wurden mit diesem Lauf neu berechnet (Chat-Review, 2026-09-22).

Weitere in diesem Lauf behobene/ergänzte Punkte: negative Grundlast wird als
Einspeisung dokumentiert statt still geklippt; T01 verschärft (keine
Toleranz mehr); P_grid/Spannungsebene durchgängig als Proxy gekennzeichnet
(`p_grid_status`, `voltage_level_status` in KPIs); StromNEV-Tarifpaarwahl
ohne Fallback auf inkonsistente Paare (empirisch geprüft: betrifft keine der
32 Standort/Konfig/Beschaffung-Kombinationen); Break-even nutzt jetzt
config.yaml:design.breakeven (max_iter=25 statt hartkodiert 10) mit
expliziter Konvergenzdiagnose; 15-min-Validierung vergleicht jetzt BASE+ELEC
über die tatsächlich berichtete Kennzahl LCOH_inc statt totex/q_useful
direkt; S10 Rolling Horizon: StromNEV-Fenster tragen keinen künstlichen
Kapazitätspreis-Term mehr je 36h-Fenster (chirurgischer Fix statt
Deaktivierung, s. Chat-Review); Regelvalidierung (R-RULE-DEV) umbenannt und
um einen KKT-Konsistenz-Check (V-04) ergänzt, s. Abschnitt 1.

## 1. Wesentliche methodische Abweichungen vom Draft (Dokument 2)

- **Bandstruktur:** Die vier Werkslastgänge liefern nur eine aggregierte
  Wärme- und eine Stromspalte (kein Temperaturkanal). Die LT/HT/VHT-
  Banddreiteilung ist daher NICHT rekonstruierbar; das Modell rechnet mit
  einem generischen Prozesswärme-Band. VHT (Metall) ist Limitation
  (Teil-3-Entscheidung #2), nicht nur für Metall, sondern strukturell für
  alle vier Standorte.
- **COP konstant:** Keine Quell-/Senktemperatur in den Rohdaten -> COP_HP
  und eta_EK/eta_GB sind zeitlich konstant (Konfigurationswert), nicht
  temperaturabhängig.
- **Modell-Zeitauflösung:** 1h statt 15min als Primärauflösung für S1-S9
  (gemessene 15min-Solvezeiten 2,5-5+ Minuten je Lauf bei ~300+ geplanten
  Läufen nicht darstellbar). 15-min-Validierungsteilmenge (2 Standorte)
  für R-TIME-01/02 und T11b.
- **strompreis_2023.csv:** Zeitstempel im Rohformat sind 2019, nicht 2023.
  Datenhalter hat am 2026-09-15 bestätigt, dass die Werte für 2023 gelten
  und nur das Datumslabel falsch ist; 1:1-Stunde-des-Jahres-Remapping auf
  2023 angewendet (s. config.yaml:prices.provenance_note).
- **S6 (1h-Zwillinge):** entfällt strukturell, da 1h jetzt die
  Primärauflösung ist; funktional ersetzt durch die 15-min-
  Validierungsteilmenge (T11b).
- **S7 (Break-even):** jetzt für BEIDE Netzregime gerechnet (16 Ketten,
  R-BE-SHIFT beantwortet); ELEC weiterhin im redispatch-Modus auf den
  jeweiligen S1-Kapazitäten (Day-Ahead-Beschaffung), nicht voll endogen
  neu ausgelegt je Preispunkt.
- **S9 (Bandanteile +-10pp):** nicht anwendbar (keine Bänder), ersetzt durch
  Wärmelast-Sensitivität +-10%.
- **S11 (COP/WACC/Risikoprämie-Sensitivität):** NICHT gerechnet (MAY-
  Priorität laut Draft-Laufmatrix, aus Zeitgründen zurückgestellt).

## 2. Unverified-Parameter mit Wirkung auf Kernaussagen (27 Stück)

Vollständige Liste in `unverified_parameters.csv`. Wirkungsreichste Posten:
StromNEV-Tarifpaare (nur MS-Paar >=2500h real belegt, alle anderen Ebenen/
Paare Literaturschätzung), AgNes k je Ebene (erlösäquivalente Konstruktion,
s. REG-02), alle Technologie-CAPEX/Wirkungsgrade (Literaturschätzungen,
keine standortscharfen Angebote), Gas-/CO2-Preis, WACC.

## 3. Offene Marker

| marker   | begruendung                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
|:---------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| REG-02   | Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung (z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) ist real und wird als Limitation benannt, nicht geglättet. |
| REG-03   | Nachrecherchiert, weiterhin offen: Der veröffentlichte AgNes-Entwurf und Presseberichte zum Konsultationsstand (2026-08-06 bis 2026-09-18) klären nicht abschließend, ob elektrische Wärmeerzeuger regulär oder in einem Sonderregime behandelt werden. Ein indirekter, für die Diskussion relevanter Befund: saisonal differenzierte Arbeitspreise wurden von der BNetzA explizit VERWORFEN, weil sie den Betrieb von Wärmepumpen deutlich verteuern würden - ein Hinweis, dass keine gezielte Verteuerung elektrischer Wärmeerzeuger beabsichtigt ist, aber keine formale Entscheidung zum Letztverbraucher-Regime. Nicht aus Daten ableitbar.                                                                                                                                                                                                    |
| REG-04   | Offen: Übergangsregelungen/Flexibilitäts-Sondernetzentgelt sind nicht Teil des Kernmodells (Draft §2.5) und daher nicht quantifizierbar. Recherche zum Konsultationsstand liefert keine über REG-01 hinausgehenden Details zu Übergangsfristen.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| R-DES-EF | n/a: VHT/E-Ofen ist gemäß Teil-3-Entscheidung #2 als Limitation behandelt (Rohdaten stützen keine VHT-Bandtrennung), daher kein EF in diesem Modell.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| BIB-02   | Offen: BNetzA-Monitoringbericht (Netzentgeltniveaus je Ebene) - s. REG-02.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

## 4. Nicht gerechnete MAY-Punkte

S11 (COP-/WACC-/Risikoprämie-Sensitivität, <=24 Läufe) wurde nicht
gerechnet. Empfehlung: bei Bedarf als eigenständige Nachlauf-Kampagne mit
dem bestehenden `run_campaign`-Mechanismus nachziehen (Muster: S5).
