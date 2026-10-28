# REPORT v9 — Umsetzung Modellkonsolidierung (Agent-Auftrag v9, 2026-10-23)

Branch `p2_v9_consolidation` (abgezweigt von `Loc_TES_Study_P2`), bearbeitet in einem ISOLIERTEN Worktree
(`p2_v9_consolidation/`), NICHT im geteilten Hauptarbeitsverzeichnis, da dort eine laufende AC/AE/AF-Solve-
Session aktiv ist (2 Jobs laut `queue.json`, nicht gestört).
Reihenfolge: A1 → A4 → A3 → A2 → B1 → B2 → B3 → B5 → B6 → C1 → C2 → B4.

## Widersprüche
Keine.

## Meldepflichten
(werden unten je Abschnitt vermerkt, falls neu)

---

## A1 — Jahresgleichheit

**Beide Reihen sind 2025, exakt dieselbe Struktur.** Modell-Eingangsdaten
(`stadtbach_acron_combined_cleaned.xlsx`: Last, Preis, Außentemperatur, WRG): `2025-01-01 00:00:00` bis
`2025-12-31 23:00:00`, **n=8.760**, durchgängig 1h-Schritte, KEINE Lücken (`diff().value_counts()` zeigt
ausschließlich `0 days 01:00:00` für alle 8.759 Differenzen). `HKW_Temp_VL.xlsx`: `2025-01-01` bis
`2025-12-31`, **365 eindeutige Tage × 24 Stunden = 8.760 Zeilen**, strukturell identisch. Keine Zeitumstellungs-
Sprünge in beiden Reihen (beide nutzen die in diesem Projekt durchgängige 8.760h-Konvention ohne DST-Korrektur
— das ist für die Modell-Konsistenz ausreichend, auch wenn keine der beiden Reihen die echte DST-Uhrzeit
abbildet). **Lücken in `HKW_Temp_VL`:** 2 fehlende/invalide Werte von 8.760 (aus v8 A2b bekannt, `Wert`-Spalte
NaN) — vernachlässigbar.
**Folge: Die Messreihe ist DIREKT als SB-HK0 verwendbar** (kein Kalibrierungsumweg nötig) — die 2 NaN-Stunden
werden mit der kalibrierten Kurve aus v8 A2b gefüllt (Interpolation wäre auch vertretbar, Kurve ist
konsistenter mit dem Rest des Modells).
Status: belegt

---

## A4 — Rücklauf als Speichergrenze

**`HKW_Temp_RL.xlsx` (2025, stündlich):** Mittel=**61,53°C**, P10=**58,2°C**, P50=**60,2°C**, P90=**66,7°C**.
Mittlerer Rücklauf in den 2.289 heutigen S1-Entladestunden: **60,42°C** (praktisch identisch zum
Jahresmittel — die Entladung konzentriert sich nicht in besonders hohen/niedrigen RL-Phasen).
**ΔT_TES = 95°C − T_RL,ref:**
- Mittel: 95 − 61,53 = **33,47 K**
- P90 (Sensitivität): 95 − 66,7 = **28,30 K**

Beide Werte sind DEUTLICH höher als der bisherige 15-K-Boden, aber auch deutlich niedriger als die 35-50K aus
der v7-D1-Hypothetisch-Rechnung (die mit den HK-Stufen-spezifischen `T_RL`-KONFIGURATIONSWERTEN, nicht der
echten Messung, gerechnet hatte).
Status: belegt (Messreihen) + berechnet (ΔT-Ableitung)

---

## A3 — Mindesttemperaturen der Verbraucher

**Nur EIN generischer Wert gefunden, keine differenzierten Werte je Industriekonsument:**
`consumer_min_temp_c: 70.0` (`Stadtbach_topo.yaml:91`), Kommentar: `"= T_return + 10 K; includes industrial
consumers (Klinikum, KUKA, MAN)"` — alle drei Industriekonsumenten werden mit DEMSELBEN pauschalen 70°C-Wert
behandelt, keine eigene, differenzierte Mindesttemperatur je Konsument im Repository dokumentiert.
**Warum fuhr die Anlage 2025 nie unter 87,4°C (v7 T3)?** KEIN Beleg/Kommentar dazu gefunden. Der generische
70°C-Mindestwert liegt deutlich UNTER der real beobachteten 87,4°C-Untergrenze — die reale Betriebspraxis ist
also konservativer als der dokumentierte Mindestwert verlangt. Mögliche Erklärungen (alle NICHT belegt, nur
plausibel): Sicherheitsmarge für Druckverlust über die Netzlänge, eine nicht dokumentierte betriebliche
Vorgabe, oder MAN/KUKA/Klinikums tatsächliche (undokumentierte) Prozessanforderungen.
Status: belegt (kein Beleg gefunden) — **Meldepflicht v9-M1:** Grund für die reale 87,4°C-Untergrenze bleibt
ungeklärt; das begrenzt, wie aussagekräftig eine HK1/HK2-Absenkung (B1b, noch nicht umgesetzt) ohne echte
Betriebs-Rückmeldung von Lukas wäre.

---

## A2 — MM-Kalibrierung

**Datenqualität unzureichend — Kalibrierung nicht durchführbar.** `Import_Data_Memmingen_epronet_cleaned.xlsx`
enthält zwar `V_n_flow_temp`/`V_n_return_temp` je Übergabestation (27 Stationen, danke für den Hinweis — meine
v8-Aussage "keine Messreihen" war zu pauschal), ABER: eine erste lastgewichtete Mittelbildung über alle 27
Stationen ergibt UNPHYSIKALISCHE Werte (Mittel ~4×10¹⁵°C, Extremwerte bis 2×10²⁰°C) — die Rohspalten enthalten
offenbar Sentinel-/Fehlercodes (z.B. -9999 o.ä.) oder Einheiten-/Dezimaltrennzeichen-Probleme, die `pd.to_numeric`
NICHT als NaN erkennt, sondern als gültige, aber physikalisch unsinnige Zahlen durchlässt. Außerdem: **43.288
Zeilen statt der erwarteten 8.760** (ungeklärtes Auflösungs- oder Mehrjahres-Problem).
**Entscheidung (gemäß B1s eigener Fallback-Klausel):** MM-HK0 behält die BISHERIGE Heizkurven-Formel
(`calculate_supply_temperature_series`) als `T_VL_ts`-Quelle — **R² kann nicht berechnet werden, da die
Eingangsdaten vor jeder Kalibrierung erst bereinigt werden müssten** (Sentinel-Wert-Filter, Auflösungsklärung).
Status: belegt (Datenqualitätsproblem) — **Meldepflicht v9-M2:** MMs Stationsmessreihen brauchen eine
Datenbereinigung (Sentinel-Filter + Plausibilitätsgrenzen, z.B. [0,150]°C) bevor eine Kalibrierung möglich ist.
Aufwand: mittel (neue Bereinigungslogik, ähnlich den bereits für SB durchgeführten Cleaning-Skripten
`scripts/preprocess/clean_stadtbach_west.py`).
**Trotzdem umgesetzt (B1):** MM wird jetzt ebenfalls durch die vereinheitlichte Injektion geführt (dieselbe
`T_VL_ts`-Reihe speist ab jetzt AUCH die Netzphysik, nicht mehr nur COP/Maske/ΔT) — das behebt bereits einen
Teil von v7 A3s Befund (Netzpfad ≠ `T_VL_ts`), auch ohne die neue Kalibrierung.

---

## B1 = E1 — Einheitliche Temperatur (umgesetzt)

**Commit `55d070f`.** `scripts/paper_2/scenario_runner.py`: `T_VL_ts` wird für SB-HK0 durch die ECHTE
2025-Messung ersetzt (`configs/paper_2/calibration/sb_hkw_temp_vl_rl_2025_hourly.csv`, aus `HKW_Temp_VL/RL.xlsx`,
2 NaN-Stunden je Reihe gefüllt — VL mit der v8-A2b-Kurve, RL mit dem Jahresmittel). Für alle anderen
Stufen/Netze bleibt die bisherige `compute_heizkurve`-Formel die Quelle, wird aber JETZT ZUSÄTZLICH als
`network.parameters.supply_temp_dict`/`return_temp_dict` injiziert — `network_manager._setup_temperatures`
bevorzugt das bereits (Prioritätsstufe 1) gegenüber `temperature_frame` (Stufe 2), keine Änderung dort nötig.
**Ergebnis:** Netzphysik (Massenstrom, Rohrverluste, Knotentemperaturen), COP, Entlademaske und Speicher-ΔT
nutzen jetzt ALLE dieselbe Reihe — für SB-HK0 die reale Messung.
`CALION_LEGACY_TEMPERATURE_FRAME=1` überspringt die gesamte Injektion (Altmodell-Pfad).
Status: umgesetzt, Build-Test folgt in C1.

## B2 = E2 — Speicher-ΔT (umgesetzt)

**Commit `9ed2a00`.** `delta_T_scenario_k` wird jetzt JE TES-ASSET aus `t_store_max_c − T_RL,ref` berechnet
(`T_RL,ref` = Jahresmittel der v9-E1-Rücklaufreihe, `CALION_TES_DELTA_T_P90=1` schaltet auf P90 um). Für SB-HK0
mit der realen Messung: `T_RL,ref=61,53°C` (Mittel) bzw. `66,7°C` (P90) → `ΔT=33,47K` bzw. `28,30K` (A4-Werte).
Die hydraulische Anbindungskappe (`power_max_mw`, z.B. die 51,8-MW-DN600-Annahme) wird LINEAR mit demselben
ΔT-Verhältnis neu skaliert (`power_max_mw_neu = power_max_mw_alt × ΔT_neu/15`) — bei SB-HK0:
51,8 × 33,47/15 ≈ **115,7 MW** (Mittel) bzw. 51,8×28,30/15 ≈ **97,7 MW** (P90).
`CALION_TES_DELTA_T_MODE=legacy_floor` restauriert die alte Formel (15-K-Boden, keine Kappen-Neuskalierung).
Status: umgesetzt, Build-Test folgt in C1.

---

## B3 = E3b — Vorwärmbetrieb (umgesetzt)

**Commit `a9ea297`.** Standard jetzt `discharge_mode="preheat"`: die binäre Maske wird NICHT mehr angewendet
(`Qd[t]` bleibt nur durch `cap_p` begrenzt), statt dessen berechnet `scenario_runner.py` je Stunde
`α(t) = max(0, (T_VL(t)−t_store_max_c)/(t_store_max_c−T_RL(t)))` (mit der v9-E1-vereinheitlichten Reihe) und
`component_assembler._finalize_couplings` fügt je TES-Asset EINE neue Constraint hinzu:
`Σ(Q_th_out anderer Assets am selben Knoten) ≥ α(t)·Qd(t)` für jede Stunde. "Am selben Knoten" wird DYNAMISCH
aus `network.nodes.<knoten>.assets` gelesen (derselben Liste, die auch das Siting nutzt) — nicht hartcodiert.
**Testfall erfüllt:** bei `T_VL(t)≤95°C` ist `α(t)=0`, die Constraint wird `Σ(...)≥0` (trivial erfüllt) — identisch
zu "Maske aus" in diesen Stunden.
**Welche Erzeuger dürfen nachheizen (geprüft, KORRIGIERT zur Auftragsannahme UND zu meinem eigenen ersten
Entwurf):** Für SB-S1 (TES an j_hkw) sind das laut `network.nodes.j_hkw.assets` NUR **`hkw`** (Gas-KWK),
**`p2h_existing`** und **`ek_sb`** (bleibt jetzt dort, E5) — NICHT "Kessel" (`hws_boiler`/`hww_boiler` sitzen an
eigenen Knoten "Heizwerk Süd"/"Heizwerk West", nicht an j_hkw) und NICHT `hp_sb`. Die Auftragsannahme "j_hkw:
HKW, Kessel, EK, KWK" trifft also auf **Kessel** NICHT zu — `hkw` selbst ist bereits die KWK-Anlage am Knoten.
**Selbstkorrektur:** meine erste Fassung dieses Abschnitts (vor dem C1-Build-Test) hatte `hp_sb` fälschlich mit
aufgeführt — tatsächlich sitzt `hp_sb` seit E5 an `j_man`, nicht mehr an `j_hkw`, ist also KEIN Geschwister von
`tes_sb` mehr. Bestätigt durch die reale Logzeile aus C1: `[PREHEAT] tes_sb (node j_hkw): topping-up generators
= ['hkw', 'p2h_existing', 'ek_sb']`.
Für MM-S1 (TES `tes_main` an `j_9`): `['chp_main', 'biomass_main', 'gasboiler_main']` — keine Standortänderung
durch E5 (nur für `network=="stadtbach"` aktiv), alle drei bestehenden MM-Erzeuger am Knoten.

**α-Statistik (nachgerechnet aus den v9-E1-Reihen, C1-Build-Test bestätigt):**
| Netz | Stunden mit α>0 (von 8.760) | Mittel wo α>0 | Max α | Mittel über alle 8.760h |
|---|---|---|---|---|
| SB (`tes_sb`, reale Messung) | 4.976 (56,8 %) | 0,268 | **0,838** | 0,152 |
| MM (`tes_main`, Heizkurve) | 84 (1,0 %) | 0,058 | **0,141** | 0,0006 |

SB liegt deutlich höher, weil die reale Messreihe (Mittel 99,9°C) den Schwellwert `t_store_max_c=95°C` sehr
viel häufiger überschreitet als MMs generische Heizkurve (Mittel 82,6°C).
`CALION_TES_DISCHARGE_MODE=mask` restauriert exakt das alte binäre Verhalten (E3a-Sensitivität).
Status: umgesetzt, Build-Test in C1 bestätigt.

## B5 = E5 — Topologie (umgesetzt)

**Commit `ac4c0a2`.** `hkw_to_man` wird zur Laufzeit `bidirectional=True` gesetzt (vorher einseitig j_hkw→j_man).
`ek_sb` wird NICHT mehr nach j_man verschoben (bleibt an j_hkw), nur `hp_sb` noch. **Einspeisepumpe/Druckhaltung
an j_man:** bereits vorhanden — `network_manager._link_pressure_propagation` behandelt JEDEN Knoten vom Typ
`mixed` (das wird j_man automatisch, sobald `hp_sb` dort sitzt) generisch als "sekundären Erzeuger" mit
schwimmendem, pumpengestütztem Druck (Zeilen 1791-1804) — KEINE neue Limitation durch die Bidirektionalität,
keine Kosten erfunden.
`CALION_LEGACY_TOPOLOGY=1` restauriert das alte Verhalten.
Status: umgesetzt, Build-Test folgt in C1.

## B6 = E6 — Neues Kostenmodell als Standard

**Kein Code-Aufwand nötig** (wie in v8 B1 bereits festgestellt) — `storage_geometry.yaml` hat das neue Modell
(Leistung bepreist 28,2k€/MW, H/D 1,5, 45m-Kappe, §4cr/§4cs) bereits UNBEDINGT als Standard; die 5
Env-Variablen (`CALION_TES_POWER_CAPEX=0 CALION_TES_HMAX=0 CALION_TES_RHD=2.0 CALION_TES_P2E_HOURS=4
CALION_TES_POWER_MAX=0`) sind der explizite Altmodell-Pfad. Keine Änderung committet, nur dokumentiert.
Status: bereits erfüllt.

---

## C1 — Build-Tests je Netz × HK0 (Pflicht, vor C2)

**Methode:** kein echtes build_only-Flag im Pipeline vorhanden (das existierende dry_run=True kehrt zu
frueh zurueck, vor T_VL_ts-Berechnung). Pragmatischer Ersatz: echter Lauf mit CALION_TIMELIMIT=15,
MIPFocus=3, Threads=4, force_rerun=True -- triggert den vollstaendigen Pyomo-Modellaufbau (und alle neuen
Logzeilen) bei vernachlaessigbarer Solve-Zeit. Zwei Laeufe, SB-S1-HK0 und MM-S1-HK0, beide liefen ohne
Traceback/Crash durch bis zur Artefakt-Extraktion (SB: 9.276.851 Zeilen, 7.139.423 Spalten; MM: 4.940.651
Zeilen, 4.467.621 Spalten -- vollstaendige Modelle, kein struktureller Fehler).

**Logzeile Temperaturpfad:**
- SB: "v9 E1: SB-HK0 network-physics temperature = REAL 2025 MEASUREMENT ... mean VL=99.9C, mean RL=61.5C"
- MM: "v9 E1: network-physics temperature = unified T_VL_ts (heating-curve formula, mean=82.6C); return
  broadcast at constant 63.6C" -- korrekt der generische Fallback (A2: MM-Stationsdaten korrupt).

**Delta_T_TES (E2):**
- SB (tes_sb): t_store_max_c(95.0) - T_RL,ref(61.53) = 33,47 K (vorher 15,00 K); Hydraulikkappe
  51,8 -> 115,6 MW.
- MM (tes_main): t_store_max_c(95.0) - T_RL,ref(63.60) = 31,40 K (vorher 15,00 K).

**E_max je Rung** (aus storage_geometry.yaml, UNVERAENDERT durch E2 -- die Leiter ist in nutzbarer Energie
[MWh] definiert, Delta_T aendert nur die implizite Volumenzuordnung, nicht die Energiestufen selbst):
- tes_sb: [0, 37, 73, 146, 219, 292, 438, 585, 731, 877, 1169, 1607, 2046] MWh.
- tes_main: [0; 0,5; 1,1; 2,2; 3,3; 4,3; 6,5; 8,7; 10,8; 13,0; 17,4; 23,9; 30,4] MWh.

**Alpha-Statistik (E3b, nachgerechnet aus der Messreihe, Max ergaenzt -- war nicht geloggt):**
- SB (tes_sb): Stunden mit alpha>0 = 4.976/8.760 (56,8 %); Mittel wo alpha>0 = 0,268; **Max alpha = 0,838**;
  Mittel ueber alle 8.760h = 0,152. Deckt sich exakt mit der Logzeile.
- MM (tes_main): Stunden mit alpha>0 = 84/8.760 (1,0 %); Mittel wo alpha>0 = 0,058 -- deutlich seltener/
  schwaecher als SB, weil die generische Heizkurve T_store_max=95C viel seltener ueberschreitet als die echte
  SB-Messreihe.

**Nachheiz-Erzeuger je TES-Knoten (component_assembler, nach E5):**
- SB: tes_sb an j_hkw -> Geschwister = ['hkw', 'p2h_existing', 'ek_sb'] (korrekt: hp_sb ist NICHT mehr
  darunter, weil E5 hp_sb nach j_man verschiebt -- nur ek_sb bleibt an j_hkw, wie B5/E5 vorgibt).
- MM: tes_main an j_9 -> Geschwister = ['chp_main', 'biomass_main', 'gasboiler_main'] (keine Standort-
  Aenderung fuer MM, E5 ist korrekt auf network=="stadtbach" gegated -- keine "v9 E5"-Logzeile im MM-Log).

**Leitungsrichtung hkw_to_man (E5, nur SB):** bidirectional=True korrekt gesetzt
("Pipe hkw_to_man: bidirectional flow_dir/m_dot_abs built (MILP mode)", max flow = 333,11 kg/s). Knoten
j_man wird automatisch type: mixed (sekundaerer Erzeuger, P_supply >= 10,0 bar pumpengestuetzt,
Druckausbreitung fuer die schliessende Schleife korrekt uebersprungen: "loop-closing pipe ... pressure
propagation skipped"). j_man: 1 lokale Erzeugungsquelle (= hp_sb) -- bestaetigt, dass ek_sb dort NICHT sitzt.

**Assertion/Fehler:** keine neuen Tracebacks, keine CRITICAL-Zeilen in beiden Logs. Die einzigen ERROR-Zeilen
sind die ERWARTETE Folge des kuenstlich auf 15s verkuerzten TimeLimit (no_incumbent, "Solver returned
aborted/maxTimeLimit without an incumbent solution") -- bei einem Modell mit >9 Mio. Zeilen ist in 15s keine
Loesung zu erwarten, das ist gewollt (Build-Test, kein Solve-Test).

**Neuer Befund (Meldepflicht v9-M3, NICHT durch v9-Code verursacht):** Der SB-Lauf meldete zusaetzlich
"INTEGRITY CHECK FAILED: pipes.csv is MM; dispatch_hourly.csv looks MM (mean demand 0.0 MW)" in seinem
EIGENEN, scenario-spezifischen Output-Verzeichnis (output/paper2_runs/SB-S1-HK0). Ursache (geprueft): NICHT
der bekannte "shared-export race" (der ist seit 2026-09-21 ueber _make_run_export_dir/output/exports/
<scenario_id>/<run_hash>/ behoben und pro Lauf isoliert) -- outdir = OUT_BASE/scen_id ist ebenfalls
scenario-spezifisch. Die Kontamination entstand, weil ich SB- und MM-Build-Test PARALLEL im selben Worktree
gestartet habe; irgendeine Zwischenablage in der Extraktionskette (output/thermal_network/..., nicht
scenario-isoliert) wurde vom zeitgleich laufenden MM-Prozess ueberschrieben, waehrend SB extrahierte. Der
MM-Lauf selbst zeigt KEINE entsprechende Kontamination (nur das erwartete "node_heat_audit.json
unreadable"). **Konsequenz fuer C2:** die zwei echten PIN0-Laeufe werden SEQUENTIELL (nicht parallel)
gestartet -- behebt das Risiko ohne Debugging einer Pipeline-Race, die ausserhalb des v9-Auftragsumfangs
liegt (B-Punkte betreffen nur E1-E6, keine Extraktions-Infrastruktur). Mittlerer Aufwand, bei Gelegenheit zu
beheben; blockiert v9 nicht.

**Fazit C1: beide Netze bauen unter dem v9-Modell fehlerfrei, alle fuenf Umsetzungen (E1/E2/E3b/E5, E6 ohne
Codeaenderung) verhalten sich exakt wie in B1-B6 dokumentiert. Freigabe fuer C2.**

---

## C2 — Ergebnisse (abgeschlossen)

Beide PIN0-Solves wurden SEQUENTIELL unter dem v9-Modell mit Matched-Effort-Settings (MIPFocus=3,
TimeLimit=28800s, MIPGap=0,0015, Threads=16, jeweils auf CPUs 0-15 gepinnt zur Koordination mit dem
parallel laufenden Peer-Job auf CPUs 16-31) gegen die Alt-Baseline gerechnet. Start erst nach Freigabe
durch Lukas (CPU/RAM-Cap combined < 50%, spaeter praezisiert auf "nur Bot-Last").

### SB-S0-HK0-PIN0

| | Alt-Baseline (v7/v8) | v9 | Delta |
|---|---|---|---|
| Status | optimal | optimal | |
| obj_eur | 23.370.804,48 | 23.314.348,08 | **-56.456,40 EUR (-0,24 %)** |
| Gap | 0,1436 % | 0,1455 % | |
| Solve-Zeit | — | 27.626,65 s (~7,67 h) | |

Kostenzeilen-Delta (v9 minus Alt-Baseline, EUR/Jahr):

| Kostenzeile | Alt-Baseline | v9 | Delta |
|---|---|---|---|
| CAPEX | 0,00 | 0,00 | 0,00 |
| Aktivierungsanteil | 0,00 | 0,00 | 0,00 |
| Brennstoff | 25.562.924,48 | 25.620.400,44 | +57.475,96 |
| Strom (Bezug) | 31.688,08 | 26.345,26 | -5.342,82 |
| Strom (KWK-Erloes, negativ) | -11.236.233,76 | -11.345.675,03 | -109.441,27 |
| CO2 (brutto) | 6.742.426,77 | 6.754.021,29 | +11.594,52 |
| Netzentgelt | 52.058,28 | 38.236,96 | -13.821,32 |
| O&M fix | 1.547.000,00 | 1.547.000,00 | 0,00 |
| O&M variabel | 667.760,28 | 671.330,13 | +3.569,85 |
| Modellhilfsterme (Summe) | 3.180,34 | 2.689,03 | -491,31 |
| **TOTAL** | **23.370.804,48** | **23.314.348,08** | **-56.456,40** |

Bilanzschluss (heat-balance-audit): residual sum=0,000 MWh, max=0,0000 MWh ueber 61.320 Bilanzen -> CLOSES
(Diagnose: ht_out=661.209 MWh, heatd=639.973,5 MWh, netloss_full=19.667,5 MWh, return=7.484 MWh,
dump=537,8 MWh). Netzverluste absolut (v9) = 19.667,5 MWh (~2,97 % von ht_out); ein quantifizierter
Alt-Baseline-Vergleichswert fuer netloss_full wurde in keinem frueheren Report gefunden (nicht verfuegbar,
daher kein Delta ausgewiesen, nur die v9-Groesse als belegt).

reconciliation_check: "OK" (Summe real+aux+residual-objective = 0,00 EUR).

### MM-S0-HK0-PIN0

| | Alt-Baseline (v7/v8) | v9 | Delta |
|---|---|---|---|
| Status | optimal | optimal | |
| obj_eur | 418.018,21 | 419.817,29 | **+1.799,08 EUR (+0,43 %)** |
| Gap | 0,1465 % | 0,1479 % | |
| Solve-Zeit | — | 2.253,6 s (~37,6 min) | |

Kostenzeilen-Delta (v9 minus Alt-Baseline, EUR/Jahr):

| Kostenzeile | Alt-Baseline | v9 | Delta |
|---|---|---|---|
| CAPEX | 0,00 | 0,00 | 0,00 |
| Aktivierungsanteil | 0,00 | 0,00 | 0,00 |
| Brennstoff | 293.967,82 | 287.839,08 | -6.128,74 |
| Strom (Bezug) | 868,03 | 1.338,94 | +470,91 |
| Strom (KWK-Erloes, negativ) | -11.250,48 | -11.370,97 | -120,49 |
| CO2 (brutto) | 35.018,00 | 33.476,54 | -1.541,46 |
| Netzentgelt | 1.126,25 | 1.541,47 | +415,22 |
| O&M fix | 76.000,00 | 76.000,00 | 0,00 |
| O&M variabel | 19.735,86 | 19.538,18 | -197,68 |
| Modellhilfsterme (Summe) | 2.552,72 | 11.454,07 | **+8.901,35** |
| **TOTAL** | **418.018,21** | **419.817,29** | **+1.799,08** |

**Befund:** alle ECHTEN Kostenzeilen (Brennstoff, CO2, Netzentgelt, O&M) bewegen sich unter v9 fuer MM in
Summe GUENSTIGER (Brennstoff -6.128,74, CO2 -1.541,46 dominieren gegenueber den kleinen Erhoehungen bei
Strombezug/Netzentgelt). Der gesamte TOTAL-Anstieg stammt fast ausschliesslich aus den Modellhilfstermen:
`Pressure_slack_cost_EUR` = 11.379,68 EUR (v9) vs. nicht einzeln ausgewiesen in der Alt-Baseline (dort nur
als Teil der 2.552,72 EUR Summe sichtbar). Label dieses Terms: "Druck-Entlastungs-Slack
(Datenqualitaets-Ventil)" — kein realer Kostenterm, sondern ein Modellierungs-Slack. Vermutung (nicht
geprueft): die v9-Topologieaenderung (E5) oder die neue Temperaturbasis (E1) aktiviert diesen Slack bei MM
staerker als unter der Alt-Baseline. **Dies ist eine offene Beobachtung fuer eine spaetere Runde, kein
Blocker fuer C2 und nicht Gegenstand dieses Auftrags (STOPP, siehe unten).**

Bilanzschluss (heat-balance-audit): residual sum=0,000 MWh, max=0,0000 MWh ueber 17.520 Bilanzen -> CLOSES
(Diagnose: ht_out=11.688 MWh, heatd=9.433,2 MWh, netloss_full=2.424,7 MWh, return=1.069 MWh, dump=9,6 MWh).
Netzverluste absolut (v9) = 2.424,7 MWh (~20,75 % von ht_out, deutlich hoeher als SB, plausibel fuer das
kleinere MM-Netz). Auch hier kein quantifizierter Alt-Baseline-Vergleichswert gefunden.

reconciliation_check: "OK" (Summe real+aux+residual-objective ≈ 0,00 EUR, Restabweichung 1,16e-10 EUR,
Rundungsrauschen).

### Fazit C2

Beide Netze loesen unter dem v9-Modell fehlerfrei und mit Gap nahe dem Matched-Effort-Ziel (0,15 %). SB
wird unter v9 guenstiger (-0,24 %), MM teurer (+0,43 %), wobei MMs Mehrpreis fast vollstaendig ein
Modellierungs-Slack-Term ist, nicht ein realer Kosteneffekt. Bilanzschluss ist fuer beide Netze exakt
(CLOSES, residual=0). **C2 abgeschlossen. Nach C2 STOPP (Auftrag v9) — keine weiteren Investitionslaeufe,
keine B4-Umsetzung, kein C3 ohne neue explizite Anweisung.**

---

## B4 = E4 — Primärquelle druckbeaufschlagter Speicher (Recherche, kein Code)

**Methode:** NICHT per WebSearch-KI-Summary. Direkter Download der Originaldokumente von der offiziellen
Danish-Energy-Agency-Seite `ens.dk/en/analyses-and-statistics/technology-data-energy-storage` (gefunden über
die offizielle ens.dk-Navigation, nicht geraten): `tech_data_energy_storage.pdf` (16,6 MB, Katalog
"Technology Data — Energy storage", ISBN 978-87-94447-46-1, Stand der genutzten Kapitel Juli 2026/Februar
2025 laut Amendment Sheet) und die zugehörige `tech_data_energy_storage_sheets.xlsx` (336 KB, strukturierte
Zahlenblätter je Kapitel) — dieselbe Quellenfamilie ("DEA/Energinet Technology Data"), die
`storage_geometry.yaml` bereits mehrfach als Primärquelle zitiert (z.B. `eta_strat: 0.85`, Leistungs-Anker
28,2k€/MW, Anschlusskosten-Bausteine).

**Befund (negativ, aber belegt): Es gibt in dieser Primärquelle KEIN Kapitel/Datenblatt für einen
druckbeaufschlagten (≥110°C) WASSER-Tank mit volumenbasierter Bepreisung.**
- Kapitel **141b "Large TTES"** (Tank-Speicher, Standardtechnologie, auf der der bestehende €250/m³-Anker
  beruht): max. Speichertemperatur **99°C** (Stickstoff-Inertisierung, DE/EN-Standard). Fußnote K im
  Datenblatt (XLSX, Zeile 48): *"Assuming the TTES is equipped with a nitrogen-based inerting system... With
  a steam-based system, however, the storage can operate at higher temperatures, typically in the range of
  100–105°C"* — **aber OHNE separate Kostenangabe**; dieselbe Spezifik-Investition
  (4,34 M€/GWh Kapazität bei 2025/est., Spanne 3,64-5,91 M€/GWh über alle Jahre/Szenarien) gilt für beide
  Varianten. DEA selbst gibt also für 100-105°C KEINEN Kostenaufschlag an.
- Kapitel **143 "Carnot Batteries and High-temperature Thermal Energy Storage"** (PDF S. 72-86, neu seit
  Feb-2025-Amendment) behandelt NUR Fest-/Flüssigsalz-Medien (143a Rock-based, 143b Molten-salt), explizit
  NICHT Wasser. Wörtliches Zitat (PDF S. 80, Abschnitt "Thermal energy storage"): *"In tank thermal energy
  storage, the thermal energy is stored in hot water contained in steel tanks (See 141 Large-scale Hot Water
  Tanks). **Pressurized versions allow for higher temperatures and greater energy density but come at
  greater complexity and higher cost. To reduce costs, mediums other than water are normally considered when
  higher temperatures are required, in order to stay at atmospheric pressure** within the storage system
  (Pressurized tanks and systems are much more costly to design, build and operate due to the increased need
  for safety considerations and added strength)."* Kein numerischer Kostenfaktor für diese Aussage gegeben
  (rein qualitativ) — und selbst wenn, wäre 143a/b (Fels/Salz) nicht direkt auf die bestehende
  Wasser-Tank-Kostenkurve (C=N·c0·((V/N)/v0)^b) übertragbar, da anderes Speichermedium (keine ρ·c_p·ΔT-Wasser-
  Physik).

**Konsequenz / zwei Optionen (keine davon umgesetzt, nur dokumentiert — B4 ist reine Recherche):**
1. Für Szenarien bis 105°C: bestehende Kostenkurve UNVERÄNDERT weiterverwenden (DEA selbst setzt keinen
   Aufschlag an) — direkt durch Fußnote K belegt.
2. Für echte ≥110°C-Druckspeicher: KEIN DEA-Primäranker verfügbar. Entweder (a) eine andere Primärquelle
   suchen (außerhalb des heutigen Umfangs), oder (b) den qualitativen DEA-Hinweis ("deutlich teurer, keine
   Zahl") explizit als "vermutet, nicht belegt" kennzeichnen, falls ein Pauschalfaktor im Modell gebraucht
   wird.
Status: belegt (Negativbefund). Primärquellen-Dateien liegen im Scratchpad (`dea_download/
tech_data_energy_storage.pdf`, `tech_data_energy_storage_sheets.xlsx`), nicht im Repo (nicht angefragt).

---
