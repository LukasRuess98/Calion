# REPORT v12 — Bilanzfix + Ergebniskampagne

Antwort auf `docs/paper_2/agent_prompts/v12_Bilanzfix.md` (Fassung v12.3, 2026-11-06). Branch `p2_v9_consolidation`, Basis 7aa6a49.
Dieser Report wird fortlaufend ergänzt. Stand: **Teil 0 und Teil A abgeschlossen**, Teil B in Arbeit.

---

## 0 — Laufende Läufe

Prüfung aller Paper-2-Prozesse von Lukas am 2026-11-06 ab 15:55 (`Win32_Process`, Kommandozeilen).

| Prozess (Wurzel-PID) | Lauf | Branch / Worktree | Betroffen nach Teil-0-Kriterium? | Maßnahme |
|---|---|---|---|---|
| 95836 `ac_scheduler.py` | Scheduler AC-Block | `Loc_TES_Study_P2` (Haupt-Worktree) | — | weiterlaufen lassen, `PAUSE` gesetzt |
| 70076 `ac_run.sh` → 73544 python | `ac7_c20_k100` SB-S1-HK0 | `Loc_TES_Study_P2` | nein (s. u.) | läuft bis Zeitlimit 86.400 s (Start 05.11. 23:06 → Ende ≈ 06.11. 23:07) |
| 25504 `ac_run.sh` → 62508 bash → 98828 python | `ac7_c20_k000` SB-S1-HK0 | `Loc_TES_Study_P2` | nein (s. u.) | **beendet 16:14:37** (Auftrag 0.3) |

Python-Prozesse mit leerer Kommandozeile und nicht lesbarem Besitzer (Wurzel 55072 u. a., gestartet 04.11. 11:14) gehören nicht zu
Lukas' Konto (`GetOwner` liefert leer) und wurden nicht angefasst. Auf `p2_v9_consolidation` lief kein Solve.

**Begründung „nicht betroffen“ (belegt):**
- `output/_ac/ac7_c20_k100/logs/scenario_runner.log` bzw. `.out`: `Pipe hkw_to_man: max flow = 333.11 kg/s (... bidirectional=False)`.
  Die Umstellung auf bidirektional existiert nur in `p2_v9_consolidation:scripts/paper_2/scenario_runner.py:337-352` („v9 E5“).
- TES an j_hkw (Primärknoten, `Placed tes_sb at node j_hkw (S1)`), WP/EK an j_man ohne Rückflussmöglichkeit.
- `hkw_to_ost` → j_ost ist bidirektional, j_ost hat keine Anlagen (`Stadtbach_topo.yaml:166`, `j_ost: {}`) und fällt nicht in den
  `Q_consumer`-Zweig.
- Die Läufe nutzen den WP-Default-Kanal (Warmstart-Referenz SB-S0: `Q_hp_def_MW` Σ 3.298,6 MWh) und das Investitions-MILP: alter Rahmen,
  kein Rechenfehler. Ergebnisse gehen nicht ins Paper.

**Durchgeführte Schritte:**
1. `output/_ac/PAUSE` angelegt 2026-11-06 16:09 (Inhalt: Begründung v12 Teil 0). Scheduler-Log 16:09:24:
   `PAUSED (output/_ac/PAUSE): no new launch; botRAM=48GB solves=2 pending=8`.
2. `ac7_c20_k100` läuft weiter (Gap zuletzt 0,154 % > Ziel 0,15 %, Schranke stagniert; Ende am Zeitlimit erwartet).
3. `ac7_c20_k000` beendet. Vorher: seit 15:27:14 kein Logeintrag (letzte Zeile: Inkumbent 2,3311e7 = TES-freie Referenz, Schranke 2,3258e7,
   Gap 0,22 %, 14.307 s), CPU-Messung 15:59: 21 CPU-s in 20 s ≈ 1 Kern (k100 im selben Fenster ≈ 15 Kerne).
   `taskkill /T /F /PID 25504` um 16:14:25 → beendet 98828 (python), 62508 (bash), 25504 (bash).
   Nachprüfung 16:14:37: **kein Prozess** mit PID oder Eltern-PID aus {25504, 62508, 98828}. Ausgabe `output/_ac/ac7_c20_k000/` (446 MB)
   nicht gelöscht; Node-File-Verzeichnis leer. Der Scheduler setzt den Job beim nächsten Zyklus selbst auf `failed` (kein `meta.json`,
   `ac_scheduler.py` `main()`), ein Neustart ist ausgeschlossen (nur `queued` wird gestartet, zudem `PAUSE`).
4. `output/_ac/queue.json`: `ac10_k010_resume` und `ac10_s20_resume` von `running` auf `aborted` (mit Notiz). Backup:
   `output/_ac/queue.json.bak_v12_teil0`.
5. Die 8 wartenden Jobs (`ac6_c20_k025_hd2`, `ac7_netz50_c20_k025`, `ac4_ref_netz50`, `ac3_monthly_free_old`, `ac7_c10_k025`,
   `ac7_c15_k025`, `ac6_c20_k025_ep8`, `ac6_c20_k025_ep12`) bleiben `queued` und durch `PAUSE` gesperrt.

Hinweis an die AC-Session: Die drei anderen lokalen Claude-Sessions (`planing-framework-for-heat-84`, `-91`, `-6f`, alle idle) erhielten
16:15 eine Nachricht, dass `PAUSE` und `queue.json` ab jetzt bei der v12-Session liegen und nichts gestartet wird. Welche davon die
AC-Session ist, ist aus der Sitzungsliste nicht ersichtlich.

`output/` ist in `.gitignore` (Zeile 38); Teil 0 ist daher nur hier dokumentiert.

---

## Widersprüche

**W1 — Änderungsliste v12 Punkt 1 vs. E6.** Punkt 1 begründet die Zeitzerlegung damit, ein engeres Ganzjahres-Gap sei „in 8–12 h nicht
erreichbar“. E6 (bindend) macht dagegen den Ganzjahreslauf (Weg A) zum bevorzugten Weg und B9 zum Ausweichweg. Umgesetzt wird E6;
Punkt 1 ist durch die Änderungen v12.1 → v12.2 überholt.

**W2 — „Warmstart je Block aus C0“ (Teil D) bei Weg A.** Weg A hat keine Blöcke. Umsetzung: Warmstart je Lauf aus dem C0-Dump derselben
Netz/HK-Stufe; „je Block“ gilt nur, falls Weg B nötig wird.

---

## Meldepflichten

**v12-M1 (NEU) — Die Primärbilanz enthält die lokale Last des Primärknotens nicht (Phantomwärme in jedem MM-Lauf).**
Im Knotenbilanz-Pfad wird die Liste der Lastknoten vollständig geleert (`calion/models/constraint_builder.py:479`,
`_all_consumer_demand_nodes = []`). Der Legacy-Pfad nimmt einen gemischten Primärknoten ausdrücklich auf (`:357-359`,
`is_primary_mixed`), der Knotenbilanz-Pfad verliert ihn. Die Primärbilanz (`:595-598`) hat danach keinen Lastterm für den eigenen
Knoten. Folge (berechnet, A1): MM j_9 (Verbraucher V_15/V_16) wird ohne Erzeugung versorgt, **252,2 MWh/a**, R_min = −0,21 MW,
1.382 h mit R < −0,05 MW (MM-PIN0 v9). SB nicht betroffen (j_hkw ohne lokale Last, belegt: `nodes_state_hourly.parquet` j_hkw = 0;
Σ Knotenlast 622.193 + j_man 17.780 = 639.973 MWh = Systemlast). Betroffen sind alle MM-Läufe seit Einführung des
Knotenbilanz-Pfads, nachweislich v7_final (MM-PIN0, MM-S1: R = −196 MWh/a), v9 und v10 (−180 MWh/a). Ohne Behebung wäre die
B1-Pflichtbedingung „MM-PIN0 → ok“ nicht erfüllbar (D0 verletzt). Behebung als **B2b** (eigener Commit, eigener Test), da
gleiche Fehlerklasse wie B2 („Bilanzfix“). Größenordnung im Zielwert (vermutet): 252 MWh × 50–70 €/MWh ≈ 13–18 k€/a, also 3–4 % des
MM-Zielwerts von rund 419 k€. In ΔTAC fällt der Term weitgehend heraus (gleiche Last in allen Designs), in absoluten MM-Werten nicht.

**v12-M2 — Grundversatz R > 0 ist ein Modelleffekt an Sammelknoten ohne Wärmebilanz (konservativ, keine Behebung nötig).**
Siehe A1. Er bleibt unter allen B1-Schwellen.

---

## A — Diagnose

Skripte: `scripts/paper_2/v12/a1_balance_from_dump.py` (R(t) aus Modellvariablen), `scripts/paper_2/v12/a1_node_residual.py`
(Residuum je Knoten). Ergebnisse je Lauf zusätzlich als `output/<lauf>/v12_a1_balance.json`.

### A1 Systembilanz

**Zeitachse (belegt).** Der Modellindex ist 1-basiert: Schlüssel in `full_solution_dump.json` sind `'1'…'8760'`,
`dump_audit.json` schreibt `str(t)` (`calion/run/result_collector.py:1489-1494`). `dispatch_hourly.csv` ist 0-basiert. Zuordnung
daher: Zeile i ↔ Modell-t = i+1. Ohne Ausrichtung entstehen scheinbare Ausschläge von ±49 MW (SB-S0, AC-Zweig); mit Ausrichtung
verschwinden sie vollständig (R ∈ [+0,02; +0,26] MW).

**Grundversatz der sauberen Referenz — Ergebnis: Modell, nicht Export (belegt).**
R aus den Modellvariablen (nicht aus den Exportspalten) für SB-PIN0 (v9):

| Größe | MWh/a |
|---|---|
| Erzeugung (8 Anlagen + hp_sb_Q) | 661.209,4 |
| Last (Modellreihe) | 639.973,5 |
| Verluste Vorlauf / Rücklauf (Σ `Q_loss_supply` / `Q_loss_return`) | 12.183,7 / 7.483,8 |
| Export `Q_loss_total_MW` | 19.667,5 (= Modellsumme, identisch) |
| Dump | 537,8 |
| **R** | **+1.030,7** (min +0,038 MW, max +0,250 MW, p50 +0,116 MW, 0 h < −0,05 MW) |

Lokalisierung je Knoten (Zufluss `Q_consumer` − Abfluss `Q_delivered` ± Erzeugung/Dump/Last; bidirektionale Leitungen
vorzeichenrichtig): j_hkw 0, j_man 0 (nach Abzug seiner in der Parquet-Datei fehlenden Last von 17.780,1 MWh),
**j_ost +884,2, j_hww +102,5, j_hws +44,0** MWh/a; Summe 1.030,7 = R. Alle drei sind reine Sammelknoten ohne Wärmebilanz
(nur Massenbilanz). Ursache (belegt, Stunde 100 / 4000): Zuleitungen in j_ost rechnen mit ΔT_eff = 53,50 / 27,10 K, Ableitungen mit
53,35 / 26,95 K (`Q_delivered·1000/(|m_dot|·cp)`). Bei erhaltener Masse geht am Knoten 0,15 K × Durchsatz an Energie verloren. Das
ist der knotenweise Vorlauftemperaturabfall (L3+-Offset), der zusätzlich zu den explizit angesetzten Vorlaufverlusten wirkt, also ein
**kleiner Doppelansatz von Verlusten in konservativer Richtung** (mehr Erzeugung als nötig). 1.031 MWh = 8,5 % der Vorlaufverluste,
0,16 % der Last. Für die AC-Referenz SB-S0 (export-basiert) ergab sich 915 MWh/a, gleiche Größenordnung.
Bewertung: keine Phantomwärme, unter allen B1-Schwellen (max |R| 0,25 < 0,5 MW; |Σ R| 0,16 % < 0,2 %); Anteil hängt nur über die
Durchsätze am Design und fällt in ΔTAC weitgehend heraus. Keine Behebung im Rahmen von v12 (Meldepflicht v12-M2).

**C1/C2 (v10) — Phantomwärme quantifiziert (berechnet, Modellvariablen):**

| Lauf | R Σ [MWh/a] | R min [MW] | h mit R < −0,05 | Dump [MWh/a] | Rückflussstunden `HKW_TO_MAN_m_dot` < 0 |
|---|---|---|---|---|---|
| SB-PIN0 (v9) | +1.030,7 | +0,038 | 0 | 537,8 | 0 |
| SB-C1 = SB-REF-HK0 (v10) | **−93.649,3** | −23,72 | 4.900 | 79.038,6 | 4.900 |
| SB-C2 = SB-S1-HK0 (v10) | **−101.070,7** | −27,49 | 4.779 | 86.067,4 | 4.779 |
| MM-PIN0 (v9) | −179,7 | −0,21 | 1.382 | 9,6 | (keine bidirektionale Leitung) |

Die Stunden mit R < −0,05 MW sind in SB-C1/C2 exakt die Rückflussstunden aus v11-A1.

Verdrängte Erzeugung gegenüber PIN0 (MWh/a, Modellvariablen):

| Anlage | C1 − PIN0 | C2 − PIN0 |
|---|---|---|
| HKW (KWK) | −43.730 | −41.674 |
| BMHKW / GTOST / AVA | −1.043 / −1.563 / −233 | −1.057 / −1.799 / +1.149 |
| Kessel HWS + HWW | −12.965 | −21.520 |
| P2H Bestand | −3.936 | −1.624 |
| **konventionell gesamt** | **−63.470** | **−66.605** |
| WP `hp_sb_Q` (davon Default-Kanal) | +47.292 (42.350) | +51.009 (46.841) |
| Dump | +78.501 | +85.530 |
| HKW-Strom | −10.418 MWh_el | −9.928 MWh_el |

In € (berechnet aus `cost_breakdown.json`, C1 − PIN0): Brennstoff −4.509.541, CO2 −1.115.927, Stromerlös +2.573.846 (weniger
Verkauf), O&M var +9.698 € → vermiedene Betriebskosten der konventionellen Erzeugung 3.042 k€ für 63.470 MWh = **48 €/MWh**.
Zielwert C1 − PIN0 = −1.364.696 €. Eine saubere Trennung „Phantom vs. echte WP-Wirkung“ ist ohne Neurechnung nicht möglich.
Untere Abschätzung des phantomgetragenen Anteils: Verdrängung über die WP-Erzeugung hinaus 63.470 − 47.292 = 16.178 MWh
(C2: 15.596 MWh) × 48 €/MWh ≈ **0,78 M€/a** (C2 ≈ 0,75 M€/a). Obergrenze: der gesamte ΔZielwert. Die Klärung kommt mit C1 (v12),
das mit B2 dieselbe Kombination ohne Fehler rechnet.

### A2 Kontaminationsinventar

| Lauf | `hkw_to_man` | Rückfluss-h | v11-M1 (j_man) | v12-M1 (Primär-Eigenlast) | Verwendbar? |
|---|---|---|---|---|---|
| v9 SB-S0-HK0-PIN0 | bidirektional (v9-E5) | **0** | nein | nein (j_hkw ohne Last) | ja, Referenz für C0 |
| v10 SB-REF-HK0 (C1) | bidirektional | 4.900 | **ja**, R = −93,6 GWh/a | nein | nein |
| v10 SB-S1-HK0 (C2) | bidirektional | 4.779 | **ja**, R = −101,1 GWh/a | nein | nein |
| v9 MM-S0-HK0-PIN0 | — (keine bidirektionale Leitung) | — | nein | **ja**, −179,7 MWh/a | nur ΔTAC-nah, nicht absolut |
| v10 MM-REF-HK0 | — | — | **nein** | **ja**, −179,8 MWh/a | dto. |
| v10 MM-S1-HK0 | — | — | **nein** | **ja**, −179,8 MWh/a | dto. |
| v7_final MM-S0-HK0-PIN0 / MM-S1-HK0 (AC-Zweig) | — | — | nein | **ja**, −196,2 / −196,3 MWh/a | dto. |
| AC-Läufe SB (`Loc_TES_Study_P2`) | unidirektional | — | nein | nein | alter Rahmen |

v9-PIN0 hat **0 Rückflussstunden** (belegt: `HKW_TO_MAN_m_dot` min 0,0, `HKW_TO_MAN_flow_dir` = 1 in allen 8.760 h). MM-REF/MM-S1 sind
von v11-M1 nicht betroffen (keine `*_flow_dir`-Variable im Dump), wohl aber von v12-M1.

### A3 Default-Kanal

- Herkunft: Commit `6b17bd9` (LukasRuess98, 2025-11-14, „Add WRG-aware heat pump COP handling and tests“), damals
  `energis/models/blocks/heat_pump.py`. Kommentar im Code: `# fallback heat` (heute `calion/models/blocks/heat_pump.py:97`).
- Formulierung: `Q = Q_wrg + Q_def` (`:239`), Strom `P_el = Q_wrg/COP(t) + Q_def/COP_default` (`:243`), COP_default = 3,0
  (`Stadtbach_topo.yaml:657` `cop_default`, `:851` `cop_fallback`; MM `Memmingen_P2_base.yaml:455/569`).
- Zweck (vermutet aus Name und Commit): Rückfallkanal, damit die WP auch in Stunden ohne WRG-Quelldaten oder bei erschöpfter
  Quelle betrieben werden kann.
- Physikalische Quelle: keine. `Q_wrg` ist durch `wrg_limit` an `WRG1Q_MW` gebunden (`:316-323`), `Q_def` hat keine
  Quellbegrenzung und keinen temperaturabhängigen COP. In C1 lieferte er 42.350 von 47.292 MWh WP-Wärme (89,6 %).

### A4 Leistungspreis — abgeschlossen

Korrekturnotiz zu v11-M2: `REPORT_v11.md:230` rechnete mit 63.620 €/MW/a. Das ist der Satz des Szenarios „Netzentgelt −50 %“
(`configs/paper_2/scenarios.yaml:425`). Der Basislauf nutzt 127.240 €/MW/a (`Stadtbach_topo.yaml:883`). (2,960 − 0,329) MW ×
127.240 €/MW = 334.768 € = berichtete Differenz (+334.769 €; in den Kostenzeilen oben C2 − PIN0 = +338.372 €, gegen PIN0 mit
dessen Spitze 0,301 MW). **Kein Doppelansatz, B3 entfällt.**
Abrechnungsart (belegt): Basis ist die **Jahresspitze**. `P_buy_peak >= P_buy[t]` für alle t (`constraint_builder.py:1067`), ein
Satz je MW und Jahr (`demand_charge_eur_per_mw_y`). Monatsabrechnung nur im Szenario `…-MONTHLY` (`scenarios.yaml:268`).
`result_collector.py:1400-1410` weist die Monatsspitzen nur zur Information aus.

### A5 WP-Strom

- `hp_sb_Pel` ist ein `pyo.Expression` (`heat_pump.py:242-249`), als `P_el_in` exportiert (`:366`) und in die globale Strombilanz
  eingetragen (`component_assembler.py:780`, `sys_buses.el_in.append(fs["P_el_in"])`).
- Strombilanz (`constraint_builder.py:27-32`): `P_buy[t] + Σ el_out[t] == Σ el_in[t] + P_sell[t]`. el_out = KWK-Strom,
  el_in = WP, P2H, EK, Pumpen (`model_finalizer.py:244`).
- WP-Strom wird damit zuerst aus KWK-Eigenstrom gedeckt (verringert `P_sell`) und erst dann aus dem Netz (`P_buy`).
  Das erklärt, warum in C1 trotz 15,7 GWh_el WP-Strom (`P_hp_el_MW` Σ 15.736 MWh) die Netzbezugskosten nur um +426 € steigen, der Stromerlös aber um 2,57 M€ sinkt.
- **Vorzeichen `Grid_sell_revenue_EUR`:** im Ergebnis-Dictionary von `result_collector.py` **positiv** (`:1417`, Erlös;
  `Grid_net_cost_EUR = energy_cost − energy_revenue`, `:1418`). In `cost_breakdown.json` (`real_costs_EUR`) **negativ** als Kostenzeile
  gespeichert (`scripts/paper_2/extract_artefacts_p2.py:293-297`, Vorzeichenkorrektur 2026-09-22). Beispiel SB-PIN0: −11.345.675 €.

### A6 Kopplungen über die Zeit (nur für Weg B relevant)

| Kopplung | Ort | in SB/MM aktiv? |
|---|---|---|
| Speicher-SOC `E[t] = E[t-1] + …` | `geometric_storage.py:586-588` | ja, sobald TES > 0 |
| Speicher zyklisch `E[last] == E0` | `geometric_storage.py:675-676` | ja |
| Leistungspreis-Jahresspitze `P_buy_peak ≥ P_buy[t]` | `constraint_builder.py:1067` | ja (Jahresspitze, A4) |
| Datenschluss-Dump-Deckel Σ_t Q_dump ≤ 0,25 % Jahreslast | `constraint_builder.py:228-276` | nur `CALION_DUMP_MODE=chp_only` |
| WP Mindestlauf-/Stillstandszeit | `heat_pump.py:269-314` | nur bei `min_uptime_h`/`min_downtime_h` > 0; in beiden Configs nicht gesetzt |
| Thermische Erzeuger Rampen / Mindestlaufzeiten | `thermal_gen.py:102-126` | nicht gesetzt (kein `max_ramp_*`, `min_uptime_h` in den Configs) |
| DSM-Rand | `dsm.py:74-75` | nicht verwendet |
| Leitungsverzögerung | `pipe_pair.py` | τ = 0 im MILP (Log: „MILP linear delay τ=0, no delay applied“); bidirektionale Leitungen ohne Verzögerung |

Fazit: Für Weg B sind nur SOC (inkl. zyklischem Rand) und die Jahresspitze echte Kopplungen.
