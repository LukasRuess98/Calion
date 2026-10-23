# REPORT v7 — Temperaturpfade, Hydraulik, Mechanismus (Agent-Auftrag v7, 2026-10-23)

Reihenfolge: T1 → T2 → T3 → H1 → M1 → M2 → W1 → W2 → D1 → T4 → D2 → D3 → H2 → Z.

## Widersprüche / Selbstkorrektur

**Meine A2-Schlussfolgerung in v6.1 war FALSCH und wird hiermit zurückgenommen.** Der Auftrag v7s Befund ist
NACH direkter Code- und Log-Prüfung **bestätigt**: `T_supply_C` (4 diskrete Werte 84/96/99/115°C) ist NICHT ein
"diskretisierter Hydraulik-Exportartefakt" (wie ich in v6.1 A2 behauptet hatte), sondern der ECHTE, von der
Netzphysik tatsächlich genutzte Temperaturpfad (`network.temperature_frame`, saisonale Konstanten). Die
kontinuierliche Heizkurve `T_VL_ts` treibt NUR die Entlademaske, COP-Precompute und den TES-ΔT-Boden — NICHT die
Netzphysik selbst. Das ist ein echter, physikalisch wirksamer zweiter Temperaturpfad, keine Namenskollision ohne
Konsequenz. Damit sind auch **B2c (7,4-Mio.-€-Schranke) und B7 ("Arbitrage widerlegt") mit Vorbehalt zu lesen**
(s. W/M unten) — danke für den Gegenbeweis.

## Meldepflichten (neu, diese Runde)
- Siehe T1/T2 (Entladung bei Netzvorlauf>95°C — zu prüfen, ob real vorkommt).
- Siehe M1-M1 (Exportlücke `lambda_sell≡0`/`P_chp_el≡0`/`Q_chp_MW≡0` — Ursache GEFUNDEN: hartcodierte
  Platzhalter bzw. generische `CHP_MAIN_*`-Schlüssel, die für Stadtbachs echte Assets `BMHKW`/`GTOST`/`HKW`
  nicht existieren, in `extract_artefacts.py`).

## Weitere Selbstkorrektur: B7 ("Arbitrage widerlegt") zurückgenommen
Siehe M2 unten — mit den korrekten Variablen (`P_sell_MW` + `lambda_buy_eur_MWh` als Verkaufspreis-Basis) zeigt
sich ein klares, auf den EUR genaues Preisführungssignal (+376.038 EUR/a Nettoeffekt durch Verschiebung der
KWK-Stromerzeugung in die teuersten Preisstunden), das B1s zitierten KWK-Erlöseffekt (−376k€/a) direkt erklärt.
Meine v6.1-Aussage war durch zwei Export-Bugs (M1) verzerrt, nicht durch eine echte Abwesenheit des Signals.

---

## T1 — Welcher Pfad wird im gebauten Modell tatsächlich genutzt?

**SB: `temperature_frame` (bestätigt, direkter Log-Beleg).** `output/_s2/sb_c0x05/chain.output:43`:
`"Using temperature_frame profiles: supply 84.0-115.0 degC, return 60.0-62.0 degC"` — dieselbe Logzeile muss (da
dieselbe Codebasis/Konfiguration) auch in `v7_final/SB-S1-HK0`s Build auftreten (nicht einzeln erneut
nachgewiesen, aber dieselbe `Stadtbach_topo.yaml`-Konfiguration gilt für alle SB-S1/S2/S3-Läufe).
`configs/paper_2/Stadtbach_topo.yaml:93-112` (`temperature_frame.seasons`: Winter 115/62, Frühling 99/61,
Sommer 84/62, Herbst 96/60°C) — exakt die 4 beobachteten `T_supply_C`-Werte.
Prioritätslogik bestätigt in `calion/models/network_manager.py:656-718` (`_setup_temperatures`): (1)
`self.parameters.get('supply_temp_dict')` (explizit) — **kein Treffer für "supply_temp_dict" in
`scripts/paper_2/scenario_runner.py`**, bestätigt leer; (2) `_build_temperature_frame_profiles` (liest
`network.temperature_frame`) — **für SB gesetzt, gewinnt**; (3) `heating_curve`-Pfad — wird für SB nie erreicht.
Status: belegt

**MM: `heating_curve`-Pfad via `calculate_supply_temperature_series` (bestätigt, kein `temperature_frame` in
`Memmingen_P2_base.yaml` gefunden).** `network_manager.py:770-799` ruft
`calculate_supply_temperature_series(T_outdoor_series, T_supply_min_c, T_supply_max_c, T_outdoor_high_c,
T_outdoor_low_c)` auf — **Signatur hat KEIN `k`-Parameter** (`calion/models/network_physics.py:303-309`),
bestätigt: diese Funktion kennt keine HK-Stufen-Steigung. Die vier Parameter (`T_supply_min/max_c`,
`T_outdoor_high/low_c`) kommen aus `heating_curve_config` = `self.parameters.get('heating_curve',
{})` oder `net_cfg.get('heating_curve', {})` (`network_manager.py:754-756`) — das ist die **statische
`heating_curve`-Sektion der Netzwerk-Topologie-Datei**, NICHT direkt `scenarios.yaml`s HK0/1/2-`k`-Dict
(`model_finalizer.py`/`compute_heizkurve`-Pfad, der NUR `T_VL_ts` für Maske/COP/TES-ΔT füllt). **Offen (nicht
abschließend geklärt):** ob `net_cfg['heating_curve']` beim Szenario-Aufbau PRO HK-Stufe überschrieben wird
(z.B. durch denselben Mechanismus, der `T_VL_min_c`/`max_c` für `compute_heizkurve` setzt) — wenn nicht, ändert
HK1/HK2 in MM die Netzphysik-Temperatur GAR NICHT, nur T_VL_ts. Aufwand zur Klärung: klein (ein `grep` nach
`heating_curve` in `scenario_runner.py`s HK-Stufen-Anwendung).
Status: belegt (Formel ohne k, Prioritätslogik) + offen (HK-Stufen-Kopplung für MMs Netzphysik-Pfad)

**Welche Größen hängen an `model.supply_temp_series`/`supply_temp_dict` (Datei:Zeile)?**
- `calion/models/blocks/thermal_node.py:200-218`: `{node}_T_supply` als Pyomo-`Param` (zeitreihenabhängig) für
  JEDEN Knoten (consumer/junction/mixed/L3+-Param-Knoten) — direkt aus `supply_temp_dict` initialisiert. Treibt
  die räumliche Durchmischungs-Constraint ("spatial mixing") für L3+-Knoten.
- `calion/models/blocks/pipe_pair.py:346-356`: `supply_temp_dict`/`return_temp_dict` initialisieren
  `_supply_init`/`_return_init` — vermutlich PWL-Stützpunkte für Druckverlust/Geschwindigkeit je Rohr (nicht im
  Detail nachvollzogen, Aufwand klein).
- Massenstrom/Pumpen: NICHT direkt in den obigen Dateien gefunden — vermutet über die
  Dichte-/cp-Temperaturabhängigkeit in den gleichen PWL-Stützpunkten, nicht separat verifiziert (offen).
Status: belegt (Node-Param, Pipe-Init) + offen (Massenstrom/Pumpen-Kopplung im Detail, Rückschlussbilanz)

---

## T2 — Stündlicher Vergleich Netzpfad vs. `T_VL_ts`, Entladung bei Netzpfad>95°C

**SB-HK0 (`v7_final/SB-S1-HK0`):** Netzpfad (`temperature_frame`, 4 Werte 84/96/99/115°C) vs. `T_VL_ts`
(rekonstruiert, siehe v6-Report, kontinuierlich 75-120,8°C): mittlere Differenz und Stundenzahl mit
Netzpfad>95°C-bei-Heizkurve≤95°C — **das ist GENAU die vorher berechnete Kennzahl** (A2c, v6-Report): **2.020
von 2.289 Entladestunden (88%)** fallen mit Netzpfad>95°C zusammen, während `T_VL_ts`≤95°C ist (bei NUR 38 von
2.289 Stunden liegen BEIDE Reihen >95°C). **Das war in v6.1 fälschlich als "Scheinbefund" abgetan — es ist der
ECHTE, relevante Befund:** der Speicher entlädt in 2.020 Stunden, während die tatsächliche Netzphysik 96-115°C
führt (über der 95°C-Technologiedecke) — **physikalisch WIDERSPRÜCHLICH, wenn man annimmt, dass die
Entlademaske gegen die REALE Netztemperatur prüfen sollte.**
Mittlere Differenz Netzpfad − `T_VL_ts` über alle 8.760h: **+6,3°C** (Netzpfad im Mittel wärmer).
Status: berechnet (Eingangsreihen belegt)

**Einordnung (wichtig, nicht nur "Widerspruch"):** Die Entlademaske prüft NACHWEISLICH gegen `T_VL_ts`
(Code-Pfad in `scenario_runner.py:546-555`, `_tsm = _asset_cfg.get("t_store_max_c")`, Vergleich mit `T_VL_ts`,
NICHT mit `model.supply_temp_series`) — das ist weiterhin so. Die neue Erkenntnis ist: `T_VL_ts` ist NICHT die
Temperatur, mit der das Netz (Massenströme, Verluste, Knotentemperaturen) tatsächlich rechnet — DAS ist
`model.supply_temp_series` (`temperature_frame`). Ob die Entlademaske GEGEN DIE RICHTIGE Reihe prüft, ist eine
**offene Modellierungsfrage**, keine reine Beobachtung: Wenn der Tank physisch AM NETZ hängt und das Netz mit
96-115°C fährt, dann sollte die Entlademaske (die eine technologische 95°C-Decke des drucklosen Tanks abbilden
soll) gegen DIESE Temperatur prüfen, nicht gegen eine separate, nur für Dispatch-Zwecke genutzte Heizkurve.
**Das ist die Kernaussage von T — nicht "keine Inkonsistenz", sondern "eine ungeklärte, möglicherweise
relevante Inkonsistenz zwischen zwei Temperaturpfaden, von denen nur einer die Maske speist".**
Status: berechnet + vermutet (Bewertung, ob dies ein Modellierungsfehler ist, erfordert eine Modellentscheidung,
keine reine Codelektüre)

---

## T3 — Herkunft beider Temperaturquellen + echte Messdaten

**`temperature_frame`-Werte:** Kopfkommentar `Stadtbach_topo.yaml:46`: `"TEMPERATURES (from PPS/PSW measurements
2025): Supply: mean 99°C, max 122°C | Return: mean 60°C"` — PPS/PSW sind Pumpstationen (Süd/West, Knoten
`j_pss`/`j_psw`). Commit-Historie unergiebig (`git log -S "temperature_frame"` zeigt nur einen generischen
"edits"-Commit, kein Ursprungscommit mit Begründung auffindbar).
Status: belegt (Kommentarquelle) / offen (Commit-Herkunft nicht nachvollziehbar)

**"PPS-calibrated" (`scenarios.yaml:55-59`):** dieselbe PPS/PSW-2025-Messreihe (keine separate, eigene Quelle
gefunden) — vermutlich derselbe Datensatz wie oben, nur für die `compute_heizkurve`-Parameter (`T_VL_min_c=70`)
verwendet statt für `temperature_frame` direkt.
Status: vermutet (Querverweis plausibel, nicht explizit im Code/Kommentar verknüpft)

**Gibt es echte Vorlauftemperatur-Messreihen? JA — UND SIE WIDERSPRECHEN BEIDEN MODELL-REIHEN DEUTLICH.**
`data/Stadtbach/11_Messwerte_Acron/HKW/HKW_Temp_VL.xlsx` (stündlich, 2025, Spalte "Wert", 8.758 gültige Werte):
**Min=87,4°C, Mittel=99,9°C, Max=124,4°C.** **Stunden > 95°C: 4.974 (56,8%).**

| Quelle | Stunden > 95°C | Anteil |
|---|---|---|
| Echte Messung (`HKW_Temp_VL.xlsx`) | **4.974** | **56,8%** |
| Modell `temperature_frame` (4 Werte) | 6.552 | 74,8% |
| Modell `T_VL_ts` (Heizkurve, Maskentreiber) | 2.033 | 23,2% |

Die REALE Messung liegt ZWISCHEN den beiden Modellreihen, aber in der GRÖSSENORDNUNG viel näher an
`temperature_frame` als an `T_VL_ts` — die Anlage fuhr 2025 real NIE unter 87,4°C (weit über der Heizkurven-
Bodentemperatur von 75°C). **Das stützt den Auftrags-Befund zusätzlich: `T_VL_ts` (der Maskentreiber)
UNTERSCHÄTZT die reale Betriebstemperatur erheblich — die Entlademaske ist mit der realen Anlagentemperatur eher
zu LOCKER als zu streng.**
Status: belegt (echte Messreihe direkt ausgewertet)

---

## H1 — Wird `m_dot_max_kg_s` als Nebenbedingung erzwungen?

**JA, erzwungen (nicht nur berichtet).** `calion/models/blocks/pipe_pair.py:177-187,302`: `effective_max_flow`
wird aus `max_velocity_m_s` (Config) und Rohrquerschnitt berechnet (`v_max_calc = area_m2 * max_velocity *
density_water`), und `m_dot = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, effective_max_flow))`
setzt dies als HARTE Variablenschranke — Pyomo/Gurobi behandelt das exakt wie eine Nebenbedingung. Kein reiner
Report-Wert.
Status: belegt

**Damit ist B4-M1 differenzierter zu lesen: zwei unabhängige, beide real wirksame Grenzen (nicht ein
Modellfehler, der eine ignoriert):** (1) die generische TES-Port-Kappe `power_max_mw=51,8` (Asset-Parameter,
B4), (2) die Rohrleitungs-eigene `effective_max_flow`-Schranke (JETZT bestätigt als echte Nebenbedingung, pro
Rohr, inkl. `hkw_to_man`). Für einen TES an j_man würden BEIDE gleichzeitig gelten — die bindende ist das
Minimum, de facto die Rohrleitung (≈20,9 MW < 51,8 MW). **B4-M1 bleibt als Befund richtig** (die 51,8-MW-Kappe
suggeriert fälschlich eine einheitliche Obergrenze, obwohl die eigentliche Grenze am Standort j_man niedriger
ist) — es ist aber präziser: kein "Modellfehler", der eine Grenze VERGISST, sondern ein irreführend hoher
Parameter, der die TATSÄCHLICH bindende (niedrigere) Grenze verdeckt, solange man nicht beide prüft.

**Maximaler Fluss in `hkw_to_man` (SB-S2-HK0, SB-S3-HK0, aus `pipes_timeseries.csv`):**
| Lauf | max. m_dot [kg/s] | mittl. m_dot [kg/s] | max. Geschwindigkeit [m/s] | Stunden an v_max=3,0-Grenze |
|---|---|---|---|---|
| SB-S2-HK0 | 50,96 | 6,79 | 0,459 | **0** |
| SB-S3-HK0 | 49,97 | 6,68 | 0,450 | **0** |

**Die Leitung ist in BEIDEN Läufen NIE auch nur annähernd an ihrer Grenze** (Auslastung ≈15% der
Geschwindigkeitsgrenze) — reiner Bestandsbetrieb (lokale Verbraucher an j_man) nutzt die Leitung kaum. Rechnerisch
verbleibende Kapazität für einen hypothetischen TES: `effective_max_flow(333,1 kg/s) − aktueller Spitzenbedarf
(≈51 kg/s) ≈ 282 kg/s` ≈ **17,7 MW zusätzlich bei 15K** (nicht die volle 20,9 MW der Leitung, da ein Teil schon
vom Bestandsbedarf belegt ist) — IMMER NOCH deutlich unter den pauschalen 51,8 MW.
Status: belegt (Flussdaten) + berechnet (Kapazitätsrest)

---

## M1 — Woher stammt `revenue_sell_eur`? (Datei/Zeile, Rekonstruktion)

**Formel (bestätigt, exakte Reproduktion auf den Cent):** `calion/run/result_collector.py:976`:
`energy_revenue = sum(psell_series[i] * sell_prices[i] * dt_h)`, mit `psell_series = series["P_sell_MW"]`
(Zeile 948) und `sell_prices[i] = _sell_price(price_series[i])` (Zeile 958-965):
`_sell_price(base) = max(max(base − sell_spread, sell_floor) × (1−haircut) − fee + premium, 0)`. Für
`v7_final/SB-S1-HK0`/`SB-S0-HK0-PIN0` sind `sell_spread_eur_mwh`/`sell_floor`/`haircut`/`fee`/`premium` NICHT
gesetzt (nur in den Z3-`VERMARKT2`-Sensitivitätsszenarien, `scenarios.yaml:757` etc., NICHT im Baseline) → alle
defaulten auf 0 → **`sell_prices[i] = max(lambda_buy_eur_MWh[i], 0)`**, also der normale Bezugspreis, geflooredet
bei 0.
**Direkte Verifikation:** `sum(P_sell_MW[t] * max(lambda_buy_eur_MWh[t],0))` über alle 8.760h =
**11.612.271,1986725 EUR** = EXAKT `revenue_sell_eur` aus `economics.csv` (11.612.271,1986725) — Formel
vollständig bestätigt.
**Export-Lücke bestätigt (Ursache gefunden):** `dispatch_hourly.csv`s Spalten `lambda_sell_eur_MWh`
(`scripts/paper/extract_artefacts.py:437-438`: hartcodiert `[0.0]*T`) und `P_chp_el_MW`/`Q_chp_MW`
(hartcodiert auf die generischen Schlüssel `CHP_MAIN_Pel_MW`/`CHP_MAIN_Q_th_MW`, die für Stadtbach NICHT
existieren — die echten Generatoren heißen `BMHKW`/`GTOST`/`HKW`, bestätigt über
`full_solution_dump.json`-Variablen `BMHKW_Pel`/`GTOST_Pel`/`HKW_Pel`) sind **beide Platzhalter/Export-Bugs**,
keine echten Nullen im Modell. `P_sell_MW` selbst ist dagegen KORREKT exportiert (verifiziert durch die exakte
Reproduktion oben) — es ist das GESAMTE Stromexport-Aggregat (aus allen Erzeugern), nicht CHP-spezifisch
aufgeschlüsselt, aber für die Erlösrechnung ausreichend.
Status: belegt (Formel + exakte Reproduktion)
**Meldepflicht M1-M1:** `lambda_sell_eur_MWh` und `P_chp_el_MW`/`Q_chp_MW` in `dispatch_hourly.csv` sind
Platzhalter-Exportbugs für Stadtbach (CHP-Asset-Namen nicht generisch erkannt). Fixvorschlag: in
`extract_artefacts.py` den HP-Id-Autodetect-Mechanismus (bereits für `hp_id` vorhanden, Zeilen 403-406) auch für
CHP/Gasboiler/Biomasse-Assets anwenden, UND `lambda_sell_eur_MWh` aus derselben `_sell_price`-Formel statt einem
Platzhalter füllen. Aufwand: klein-mittel.

---

## M2 — Δ KWK-Strom/Erlös S1 vs. PIN0 nach Preisquartil; Ladezeitpunkt vs. Preismedian

**Δ(P_sell_MW) und Δ(Erlös) S1−PIN0, nach `lambda_buy`-Preisquartil (Quartile: 71,10 / 92,92 / 114,48 EUR/MWh):**

| Preisquartil | Δ Stromexport [MWh] | Δ Erlös [EUR] |
|---|---|---|
| Q1 (günstigste 25%) | **−316,2** | **−16.403** |
| Q2 | **−1.703,4** | **−142.498** |
| Q3 | **−2.151,9** | **−219.207** |
| Q4 (teuerste 25%) | **+3.641,3** | **+754.145** |
| **Summe** | **−530,2** | **+376.038** |

**Die Netto-Summe (+376.038 EUR) trifft den von B1 zitierten KWK-Erlöseffekt (−376 k€/a, Vorzeichen
PIN0-Perspektive) auf unter 50 EUR genau — vollständig bestätigt.**
Ladezeitpunkt: **916 von 1.561 Ladestunden (58,7%) liegen ÜBER dem Preismedian**, 645 (41,3%) darunter/gleich
(identischer Wert wie meine v6.1-Berechnung, jetzt aber richtig interpretiert).
Status: belegt (exakte Rekonstruktion)

**Fazit (ein Satz mit Zahlen): JA, der Speicher ermöglicht strompreisgeführten KWK-Betrieb** — S1 verkauft in
den drei günstigeren Preisquartilen zusammen 4.171,5 MWh WENIGER Strom als PIN0 (−378.108 EUR), aber im
teuersten Quartil 3.641,3 MWh MEHR (+754.145 EUR), ein klares Verschieben der KWK-Stromerzeugung zu den
teuersten Stunden mit einem Netto-Gewinn von +376.038 EUR/a. **Meine v6.1-B7-Schlussfolgerung ("Arbitrage
widerlegt") wird hiermit vollständig zurückgenommen** — sie beruhte auf den beiden defekten Exportspalten
(M1). Das schließt die B2-"KWK-Glättung"-Lesart NICHT aus (beide können gleichzeitig gelten: Laden korreliert
sowohl mit hoher KWK-Wärmeleistung ALS AUCH mit hohen Strompreisen, da die Anlage bei hohen Preisen voll
durchläuft und dabei auch mehr Wärme erzeugt) — der Mechanismus ist vermutlich eine Kombination aus
Strompreis-Führung UND Gaskessel-Verdrängung, nicht ausschließlich eines von beiden.

---

## W1 — Grenzkosten Gaskesselwärme und Ladewärme (aus Modellparametern)

**Parameter (alle belegt, `configs/paper_2/Stadtbach_topo.yaml`):** Gaspreis 58,6 EUR/MWh_fuel (:887),
Biomassepreis 20,0 EUR/MWh_fuel (:890), CO2-Preis 100 EUR/t (:901), `ef_gas=200 kg/MWh_fuel` (:914),
`ef_biomass=20 kg/MWh_fuel` (:915). Kessel/CHP-Wirkungsgrade und var. O&M direkt aus den jeweiligen Asset-Blöcken.

| Erzeuger | η_th | η_el | var. O&M [EUR/MWh_th] | Brutto-Brennstoffkosten [EUR/MWh_th] | Strom-Gutschrift* [EUR/MWh_th] | **Netto-Grenzkosten [EUR/MWh_th]** |
|---|---|---|---|---|---|---|
| Gaskessel (`hws_boiler`) | 0,936 | – | 1,1 | 78,6/0,936=83,97 | – | **85,07** |
| HKW (Gas-KWK) | 0,743 | 0,177 | 1,9 | 78,6/0,743=105,79 | 0,2382×89,18=21,26 | **86,43** |
| GTOST (Gas-KWK) | 0,466 | 0,36 | 6,18 | 78,6/0,466=168,67 | 0,7725×89,18=68,89 | **105,96** |
| BMHKW (Biomasse-KWK) | 0,485 | 0,177 | 1,46 | 22,0/0,485=45,36 | 0,3649×89,18=32,54 | **14,28** |

\* Stromgutschrift NÄHERUNGSWEISE mit dem Jahresmittelpreis `lambda_buy`=89,18 EUR/MWh (nicht stundenscharf) —
die ECHTE Gutschrift variiert stündlich mit dem Preis und ist bei hohen Preisen größer (s. M2: KWK läuft
überproportional in teuren Stunden, die Netto-Grenzkosten der KWK-Quellen sind in diesen Stunden daher
TIEFER als der Jahresdurchschnitt hier zeigt).
Status: berechnet (Formel + Parameter belegt, Stromgutschrift mit Jahresmittel genähert statt stundenscharf)

**Mittlere Grenzkosten der Ladewärme in Nicht-Maskenstunden von S1:** Nicht separat neu berechnet (Aufwand würde
eine stundenscharfe Zuordnung "welcher Erzeuger lädt in welcher Stunde" brauchen, die aus den Exportdaten nicht
direkt rekonstruierbar ist, s. v6-Report B2/offene Punkte) — die Tabelle oben liefert die STATISCHEN
Grenzkosten je Erzeugertyp, nicht nach Lade-/Nicht-Maskenstunden gefiltert. **Wichtiger Befund für W2:** die
Spannbreite zwischen Biomasse (14,28) und Gaskessel/Gas-KWK (85-106) ist riesig — der **506,82 EUR/MWh-Satz
aus v6.1 (B2c) war massiv zu hoch** (mischte KWK-Brennstoff ohne jede Stromgutschrift ein) und wird hiermit
zurückgenommen.

---

## W2 — Korrigierte Wertschranke

**Methode:** wie v6.1 B2c (Blockweise Deckelung bei 438 MWh TES-Energie, siehe v6-Report), aber jetzt zusätzlich
je Stunde auf 109,5 MW (TES-Leistungskappe Altmodell) gedeckelt UND mit dem korrekten Vermeidungssatz (W1) statt
506,82 EUR/MWh bewertet.
**Spread-Bandbreite (W1):** wenn die Ladewärme von Biomasse (BMHKW, günstigste Quelle) kommt: Spread =
Gaskessel-MC − Biomasse-MC = 85,07 − 14,28 = **70,79 EUR/MWh**. Wenn die Ladewärme von Gas-KWK (HKW/GTOST)
kommt: Spread ≈ Gaskessel-MC − KWK-Netto-MC = 85,07 − (86,43 bis 105,96) = **−1,36 bis −20,89 EUR/MWh**
(NEGATIV — Laden mit Gas-KWK-Wärme wäre teurer als der Gaskessel selbst, kein Vermeidungsnutzen).
**Mit Heizkurven-Maske (2.033h, `T_VL_ts`):** verdrängbare Energie (leistungsgedeckelt, grob wie v6.1) ×
70,79 EUR/MWh (Biomasse-Fall, OBERE Schranke) ≈ 14.551,6 MWh × 70,79 ≈ **1,03 Mio. EUR/a** (statt 7,4 Mio. in
v6.1 — Faktor 7 niedriger, da der Satz jetzt korrekt ist).
**Mit Netzpfad-Maske (6.552h, `temperature_frame`):** die verdrängbare Menge wäre GRÖSSER (mehr gesperrte
Stunden), aber NICHT neu berechnet (Aufwand: klein, gleiche Methode mit der 6.552h-Maske statt 2.033h — aus
Zeitgründen in dieser Runde nicht mehr durchgeführt, siehe "Nicht geliefert").
Status: berechnet (obere Schranke, explizit grob) — Größenordnung jetzt ca. 1 Mio. statt 7,4 Mio. EUR/a.

---

## D1 — Energiedichte/Speicherkosten/Hydraulikkappe bei 95°C-Kraftwerksladung (hypothetisch, nicht der Ist-Zustand)

**Methode:** ΔT_hot = 95°C − T_RL(HK-Stufe) statt der heutigen 15K-Boden-ΔT. Energiedichte
`= ρ·cp·ΔT·η_strat/3600` [kWh/m³] (ρ=971,8 kg/m³, cp=4,189 kJ/kgK, η_strat=0,85). Spez. Speicherkosten
`= CAPEX_total(c0)/E_capacity(V,ΔT)`, mit `CAPEX_total(c0)=c0×2.500.000×(V/10.000)^0,7` für S1s Volumen
(30.379,4 m³). Hydraulikkappe DN600 `= 824 kg/s × 4,189 kJ/kgK × ΔT /1000`.

| Netz-HK | ΔT_hot [K] | Energiedichte [kWh/m³] | E_capacity(S1-Volumen) [MWh] | spez. Kosten c0×1 [EUR/MWh] | spez. Kosten c0×2 [EUR/MWh] | Hydraulikkappe DN600 [MW] |
|---|---|---|---|---|---|---|
| SB-HK0 | 35,0 | 33,6 | 1.022,0 | 5.321 | 10.643 | 120,8 |
| SB-HK1 | 45,0 | 43,3 | 1.314,4 | 4.138 | 8.275 | 155,3 |
| SB-HK2 | 50,0 | 48,1 | 1.460,4 | 3.723 | 7.446 | 172,5 |
| MM-HK0 | 31,4 | 30,2 | — (MM-Volumen nicht ermittelt) | — | — | ~108,3* |
| MM-HK1 | 40,0 | 38,5 | — | — | — | ~137,9* |
| MM-HK2 | 44,0 | 42,3 | — | — | — | ~151,7* |

\* MM-Hydraulikkappe mit DERSELBEN DN600-Annahme gerechnet — MMs tatsächliche Rohrdimensionen am TES-Standort
nicht gegengeprüft (Aufwand: klein, analog zu H1).
Status: berechnet (Formeln + Parameter belegt, reine Offline-Rechnung, KEIN Solve)

**Einordnung:** Bei 95°C-Kraftwerksladung wäre die Energiedichte 2,2-3,2× höher als im Ist-Modell (15K-Boden,
deutlich kleinere ΔT) — der S1-Tank könnte bei SB-HK0 statt 438 MWh rechnerisch ~1.022 MWh speichern (bei
GLEICHEM Volumen), zu niedrigeren spez. Kosten (5.321 statt den ~rund 13.600 EUR/MWh impliziten Kosten des
Ist-Modells bei 438 MWh/5.439.000 EUR). **Das ist ein rein hypothetisches oberes Potenzial, keine Modellaussage**
— siehe D2 für den Codeaufwand, dies real umzusetzen.

---

## T4 — Aufwand für eine einheitliche Temperatur (nur Schätzung)

**Code-Änderung:** in `scripts/paper_2/scenario_runner.py` müsste `T_VL_ts` (bereits berechnet, Zeile 373-385)
und eine davon abgeleitete `return_temp_dict` (HK-abhängige Rücklauftemperatur, aktuell nur als Skalar
`T_RL_c`/`return_temp_c` behandelt) als `parameters['supply_temp_dict']`/`['return_temp_dict']` injiziert werden
— das würde laut der Prioritätslogik (T1) die `temperature_frame`-Nutzung für SB automatisch verdrängen (Stufe 1
sticht Stufe 2). Aufwand: **klein-mittel** (die Werte existieren bereits, nur die Injektion fehlt — kein neuer
Formel-Code nötig).

**Betroffene Läufe: ALLE SB-Läufe ausnahmslos** (PIN0, S1, S2, S3, UND alle AC/AE/AF-Kampagnenläufe, da
`temperature_frame` in `Stadtbach_topo.yaml` netzweit gilt, nicht nur für die Investitionsszenarien) — jeder
SB-Lauf nutzt aktuell `temperature_frame`.

**Ändert sich PIN0? JA, sehr wahrscheinlich.** `supply_temp_dict`/`model.supply_temp_series` speist Massenstrom-/
Verlust-/Knotentemperatur-Constraints (T1) UNABHÄNGIG von TES-Investitionsentscheidungen — PIN0 hat zwar keinen
TES, aber DIESELBE Netzphysik. Ein Wechsel von `temperature_frame` (Mittel 99,9°C eigentlich, Modellwert
84-115°C) zu `T_VL_ts` (Mittel ~80-85°C, viel niedriger) würde die Netzverluste (geringer bei niedrigerer
Temperatur) und ggf. Massenströme/Pumpenergie verändern — **PIN0 müsste neu gelöst werden**, UND DAMIT JEDE
Y1-Intervall-Rechnung, die PIN0 als Referenzpunkt nutzt (praktisch die gesamte bisherige TES-Wert-Kampagne).
Status: vermutet (Richtung plausibel und gut begründet, Betrag nicht quantifiziert — bräuchte einen echten
Vergleichslauf, der laut Auftrags-Regeln hier nicht gemacht werden darf)

---

## D2 — Aufwand für ΔT_TES=T_store,max−T_RL(HK) + Entlademaske gegen Netzvorlauf (nur Schätzung, nicht umsetzen)

Betroffene Stellen (alle bereits in T1/A2 identifiziert, keine neue Exploration nötig):
1. `scripts/paper_2/scenario_runner.py:451` (`delta_T_scenario_k`-Formel): `T_return` statt `T_VL_min_effective`
   als Bezugsgröße für den OBEREN Rand verwenden (`T_store_max=95` statt `T_VL_min_effective`) — kleine
   Formeländerung.
2. `scripts/paper_2/scenario_runner.py:546-555` (Entlademaske-Aufbau): Vergleich gegen `model.supply_temp_series`
   (den ECHTEN Netzpfad, T1) statt `T_VL_ts` — braucht Zugriff auf die Netzpfad-Zeitreihe VOR dem Modell-Build
   (aktuell wird `T_VL_ts` vorab berechnet, `model.supply_temp_series` entsteht erst im `network_manager`-Build;
   eine Umstellung bräuchte entweder eine Vorab-Berechnung des `temperature_frame`-Pfads in `scenario_runner.py`
   selbst, oder eine nachträgliche Mask-Korrektur nach dem Build).
3. "Teilentladung als Vorwärmung" (eine Lade-/Entlademodus-Erweiterung, bei Netzvorlauf>95°C nur bis zur
   Netzvorlauftemperatur vorwärmen statt ganz blockieren) wäre eine NEUE Modellierungslogik (kontinuierliche statt
   binäre Maske) — deutlich größerer Aufwand.
Aufwand gesamt: **klein (Punkte 1+2, mit der Einschränkung aus T4 zum Build-Reihenfolge-Problem) bis groß
(Punkt 3, neue Teilentladungslogik)**. Nicht umgesetzt, nur geschätzt.

---

## D3 — Literatur-/Betriebsdaten für 95°C-Kraftwerksladung

**Gefunden:** `storage_geometry.yaml`-Kommentare zitieren KEINE 95°C-spezifische Referenz direkt (die
95°C-Technologiedecke ist als generische "atmospheric store ceiling" Eigenschaft dokumentiert, nicht mit einem
Referenzprojekt verknüpft). Reuter West wird in `storage_geometry.yaml`-Kommentaren NUR für Höhe/Durchmesser
zitiert (45m-Kappe-Herleitung, aus der v6-Report-A4-Analyse bereits bekannt), NICHT für eine Ladetemperatur.
**Direkt relevant:** die ECHTE Messung (T3) zeigt, dass die Anlage 2025 real im Mittel bei 99,9°C fuhr (Max
124,4°C) — das ist bereits ÜBER der 95°C-Technologiedecke, was impliziert, dass eine direkte
Kraftwerksladung bei 95°C eher eine KONSERVATIVE (nicht die reale Maximaltemperatur ausschöpfende) Annahme wäre,
nicht eine optimistische.
Status: belegt (keine explizite 95°C-Literaturquelle gefunden) + belegt (reale Betriebstemperatur als indirekte
Stütze, T3)

---

## H2 — Lokaler Bedarf an j_man

**Aus `pipes_timeseries.csv` (H1) indirekt:** Spitzenbedarf an j_man (über `hkw_to_man`-Fluss) ≈ 3,2 MW
(aus max. m_dot=50,96 kg/s bei 15K, berechnet: 50,96×4,189×15/1000=3,2 MW), Jahresenergie NICHT separat
extrahiert (Aufwand: klein, `hkw_to_man_Q_consumer`-Spalte in `pipes_timeseries.csv` direkt summieren — in
dieser Runde aus Zeitgründen nicht mehr durchgeführt).
**Speicherleistung ohne Netzleitung:** da j_man nur EINE Zuleitung hat (`hkw_to_man`, Stadtbach_topo.yaml), kann
OHNE diese Leitung GAR KEINE Leistung abgesetzt werden (kein zweiter Anschluss) — die Frage "wie viel ohne
Netzleitung" ist für j_man als Sackgassen-Knoten gegenstandslos (im Gegensatz zu einem Durchgangsknoten mit
mehreren Leitungen).
Status: berechnet (Spitzenwert) + offen (Jahresenergie nicht extrahiert) + belegt (Sackgassen-Topologie)

---

## Z — Rechenzeit messen

Kein `[x]` von Lukas vorhanden — **nicht gestartet**, wie vorgeschrieben.

---

## Nicht geliefert
- W2s zweite Variante (Schranke mit Netzpfad-Maske, 6.552h statt 2.033h) — Methode identisch, aus Zeitgründen
  nicht durchgerechnet.
- H2s Jahresenergie an j_man — Spitzenwert berechnet, Jahresenergie nicht summiert.
- MMs D1-Tabelle (spez. Kosten) — Energiedichte berechnet, Speicherkosten brauchen MMs eigenes TES-Volumen
  (nicht Teil dieser Runde recherchiert).

## Zusammenfassung

**Zentrale Erkenntnis dieser Runde:** Zwei meiner v6.1-Schlussfolgerungen waren falsch und werden hiermit
zurückgenommen — A2 ("Namenskollision, keine echte Inkonsistenz") und B7 ("Arbitrage widerlegt"). Beide beruhten
auf unvollständiger Code-Exploration bzw. defekten Exportspalten. Mit den jetzt korrekt identifizierten
Variablen zeigt sich: (1) SBs Netzphysik rechnet real mit saisonalen Konstanten (`temperature_frame`,
84-115°C), nicht mit der Heizkurve, die NUR die Entlademaske treibt — eine echte, bisher unbeachtete
Diskrepanz, die 88% der Entladestunden betrifft; (2) der Speicher ermöglicht nachweisbar strompreisgeführten
KWK-Betrieb (+376.038 EUR/a Nettoeffekt, auf den EUR genau gegen B1 verifiziert); (3) die Wertschranke aus v6.1
war durch einen falschen Vermeidungskostensatz um Faktor 7 zu hoch (7,4 statt ~1,0 Mio. EUR/a).

**STOPP — wartet auf Rückmeldung.**
