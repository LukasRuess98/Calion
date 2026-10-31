# REPORT v10 — Prüfpunkte + Kernlaufsatz Modell v9

Antwort auf `docs/paper_2/agent_prompts/v10_Kernlaufsatz.md`. Basis: Tag `p2-v9-model`, Branch `p2_v9_consolidation`.
Status: Teil A + B abgeschlossen; Teil C läuft (siehe Zeitplan unten).

---

## A1 — MM `Pressure_slack_cost_EUR` (11.380 EUR/a in v9-PIN0)

**Methode:** direkte Auswertung der v9-C2-Laufdaten (`output/paper2_runs/MM-S0-HK0-PIN0/`), kein neuer Lauf.

### (a) Ort, Zeitpunkt, Kosten

Es existiert GENAU EIN Slack-Term im gesamten Modell: `J_13_station_dp_slack` (Pumpstation an Knoten j_13).
Aus `pressure_slack_audit.json`: **6 von 8.760 Stunden** mit Slack > 0, alle im Dezember:

| Stunde | Datum/Zeit | Slack [bar] |
|---|---|---|
| 8365 | 2025-12-15 12:00 | 3,2564 |
| 8366 | 2025-12-15 13:00 | 3,2564 |
| 8367 | 2025-12-15 14:00 | **3,3118 (Jahresmax)** |
| 8413 | 2025-12-17 12:00 | 0,2168 |
| 8414 | 2025-12-17 13:00 | 0,2168 |
| 8415 | 2025-12-17 14:00 | 1,1215 |

Summe 11,3797 bar·h × 1.000 EUR/bar·h = 11.379,68 EUR (reproduziert den Modellwert exakt). Monatsverteilung: 100 %
Dezember, 0 % alle anderen Monate. Status: belegt (Rohdaten).

### (b) Hypothesenprüfung: Spreizung, Massenstrom, Druckverlust

Bestätigt aus `dispatch_hourly.csv` (v9-PIN0, ganzjährig): **T_supply_C Mittel = 82,54 °C** (Hypothese: 82,6 °C),
**T_return_C konstant = 63,6 °C**, **Spreizung Mittel = 18,94 K** (Hypothese: ≈19 K). Die v8-A3-Referenz
("Netzpfad" HK0, `temperature_frame`-Pfad) lag bei **Mittel 91,9 °C** (also ΔT_alt ≈ 91,9−63,6 = 28,3 K) — die
Spreizung sinkt unter v9 von ≈28,3 K auf 18,94 K.

Massenstrom/Druckverlust an der betroffenen Leitung `j11_to_j13` (Trunk zur Pumpstation j_13), aus
`pipe_state_hourly.parquet`:

| | Jahresmittel | Jahresmax | An den 6 Slack-Stunden |
|---|---|---|---|
| m_dot [kg/s] | 1,975 | **20,509** | 16,0–20,5 (= Jahresmax-Bereich) |
| dp [Pa] | 5,41 | **10.785,47** | 3.609–10.785 (= Jahresmax-Bereich) |

**Die Slack-Stunden SIND die 1-2 Stunden mit dem höchsten Massenstrom/Druckverlust des gesamten Jahres** auf
genau der Leitung, die zur Pumpstation führt — kein Zufall, sondern der Extremfall der Hypothese.
`j13_to_j14`/`j13_to_j15` (die Abzweige nach j_13) zeigen `dp_Pa=0,0` ganzjährig (bereits aus früheren Runden
bekannte PWL-Tangenten-Envelope-Lockerheit bei niedriger Auslastung, kein neuer Befund).

Massenstrom-Skalierung (aus der Energiebilanz Q=ṁ·cp·ΔT, demand-seitig unverändert): ΔT_alt/ΔT_neu =
28,3/18,94 = **1,494** → **+49,4 % Massenstrom** (Hypothese: ~45 %, Größenordnung bestätigt). Druckabfall ist im
Code quadratisch in ṁ linearisiert (`pipe_pair.py`: "Δp = k_flow·ṁ² ... PWL-Tangenten-Lower-envelope"), also
**+(1,494²−1) = +123 % Druckverlust** rechnerisch erwartet — konsistent mit dem beobachteten Sprung von
Jahresmittel (5,41 Pa) auf Jahresmax (10.785 Pa) an genau den kältesten Stunden.
Status: belegt (Code, reale v9-Laufdaten) + berechnet (ΔT→ṁ²→Δp-Skalierung; kein Alt-Modell-Lauf mehr auf
Platte vorhanden, um die exakte historische Δp-Reihe gegenzurechnen — die v7/v8-PIN0-Dispatchdaten für MM
wurden beim v9-C2-Lauf unter derselben scenario_id überschrieben).

### (c) Einschätzung: hydraulisch nicht fahrbar?

**Nein, nicht im Sinne einer harten Infeasibilität — aber ein genuiner, erklärbarer Rückgang der hydraulischen
Reserve an der kältesten Stelle des Jahres.** Begründung: nur 6 von 8.760 Stunden (0,07 %) betroffen, Slack-
Summe 11,38 bar·h bei einem künstlich günstigen "Letzte-Instanz"-Strafpreis (1.000 EUR/bar·h) — der Mechanismus
ist bewusst als Ventil gebaut, kein Hinweis auf echte Infeasibilität des Netzes. Die physikalische Kette
(niedrigere Spreizung → höherer Massenstrom → quadratisch höherer Druckverlust → Druckhaltung bindet exakt an
der kältesten Stunde) ist jedoch real und reproduzierbar — die Heizkurve fährt unter v9 hydraulisch näher am
Limit als unter der alten Formel. **Offene Frage für jeden MM-Vergleich (STOPP-Regel):** Die STOPP-Regel
(Hilfsterme > 20 % des Δ) greift auf die DIFFERENZ zwischen zwei Szenarien, nicht auf den Absolutwert. Ob der
11,38k-EUR-Slack bei C3 (MM-S1 mit TES an j_9, weit von j_13) überhaupt eine signifikante Δ erzeugt, hängt
davon ab, ob die TES-Investition den Massenstrom an j_13 ändert — das ist unbekannt, bis C3 real gelöst ist.
Diese Prüfung wird in C3 explizit nachgeholt (siehe dort).
Status: belegt (Zahlen) + vermutet (Einschätzung "kein Infeasibilitäts-Hinweis", qualitativ, nicht jeder
denkbare Gegenfall ausgeschlossen).

---

## A3 — Maske im Vorwärmmodus + Robustheits-Fix

**Code-Beleg (stärker als Log-Grep, da strukturell statt zufällig im Log vorhanden):**
`geometric_storage.py:640`: `qd_mask`-Constraint wird NUR gebaut, wenn `self.discharge_mode == "mask"`.
`geometric_storage.py:713-714`: `preheat_alpha_ts` (Voraussetzung für die Topping-Constraint) wird NUR
gesetzt, wenn `self.discharge_mode == "preheat"`. `component_assembler.py:693`: die eigentliche
`{tes_id}_preheat_topping`-Constraint wird NUR gebaut, wenn `preheat_alpha_ts` nicht `None` ist. Die beiden
Modi sind also strukturell exklusiv — im Default (`preheat`, v9 E3b) existiert `qd_mask` nicht, nur
`*_preheat_topping`.
Status: belegt (Code, drei sich gegenseitig stützende Fundstellen)

**Robustheits-Fix (eigener Commit `733e97a`):** `"T_RL_ts" in dir()` / `locals().get("T_RL_ts")` (Zeilen 585,
759 vor dem Fix) ersetzt durch eine unbedingte `T_RL_ts = None`-Bindung vor dem E1-Block plus einfache
`is not None`-Prüfungen. Keine Verhaltensänderung. **Testfall bestanden:** MM-α-Statistik vor/nach Fix
identisch (n_pos=84, mean_pos=0,0578, max=0,1408).
Status: belegt (Diff + Testlauf)

---

## A2 — Ladeseite des Tanks

**Code-Befund:** `component_assembler.py:_finalize_couplings` zeigt zwei Pfade für die Tank-Ladung (`Qc`,
intern `Q_th_in`):
1. **Hot-Charging-Kopplung** (`hot_charging: true`, S3-Szenarien): `Qc[t] == Q_hot[t]` — ein GESCHLOSSENES
   Rohr direkt von der WP zum Tank, `Qc` ist dafür explizit VOM generischen Knotenbus genommen ("the TES Qc
   was kept OFF the node bus in anticipation of this coupling — without it, charging would be free energy").
2. **Standardfall (kein hot_charging, z.B. S1 an j_hkw, S2 an j_man):** `Qc` bleibt auf dem generischen
   Knotenbus — die Ladewärme kommt aus EINER gemeinsamen Knotenbilanz, die Knotenerzeuger (hkw, p2h_existing,
   ek_sb bei j_hkw) UND Netzzufluss über Leitungen UNDIFFERENZIERT mischt. Es gibt keine Nebenbedingung, die
   verlangt, dass die Ladewärme speziell aus 95°C-fähigen Quellen stammt.

**Damit bestätigt A2 die im Auftrag vermutete Asymmetrie:** die Entladeseite hat seit E3b eine explizite
Nachheiz-Pflicht (Serienschaltung Tank→Nachheizer), die Ladeseite hat KEINE analoge Bedingung — ein TES im
Standardfall kann rechnerisch mit Netzwasser < 95°C "laden", was E2s Energiedichte-Annahme (ΔT bis 95°C)
verletzt. Status: belegt (Code, drei Fundstellen)

**Quantitativ (Stunden mit T_VL < 95°C):** aus der REALEN Messreihe (`HKW_Temp_VL.xlsx`, dieselbe Reihe, die
v9 E1 jetzt direkt injiziert, also kein Umweg über eine veraltete Dispatch-Kopie nötig): **3.784 von 8.758
Stunden (43,21 %)** mit T_VL ≤ 95°C (Min 87,4°C, Mittel 99,88°C, Max 124,4°C) — bestätigt die Auftrags-Zahl
"43 %" exakt.

**Erzeuger-Deckungsfähigkeit (Lesen/Rechnen, KEIN neuer Lauf):** Der ursprünglich geplante Weg — die
v7-S1-Dispatchdaten direkt auswerten — ist nicht mehr möglich: **`output/paper2_runs/SB-S1-HK0` wurde
zwischenzeitlich durch einen Build-Test (2026-10-23, `status=no_incumbent`) überschrieben; die reale v7/v8-
Investitions-Dispatchreihe existiert auf dieser Platte nicht mehr** (derselbe strukturelle Risiko-Typ wie
bereits für die SB/MM-PIN0-Altbaseline in v9-C2 dokumentiert). Auch das Archiv `output/v7_final/` (referenziert
in `B4_konvergenz_provenienz.csv`) ist nicht mehr auf der Platte. **Meldepflicht v10-M1.**

Als Ersatz (Konfigurationsdaten, nicht an einen Lauf gebunden, daher weiterhin "Lesen/Rechnen"): Nennleistung
der Knotenerzeuger an j_hkw aus `Stadtbach_topo.yaml`: hkw=127,0 MW_th + p2h_existing≈9,8 MW_th (9,9 MW_el ×
0,99) = **136,8 MW_th fest verfügbar** (ek_sb kommt als Investition potenziell hinzu, Basis=0 MW). Der
hydraulische Lade-Leistungsdeckel von `tes_sb` unter v9 E2 (ΔT=33,47K) beträgt **115,6 MW** (Build-Log-Zitat,
`SB-S2-HK0`: "hydraulic connection cap rescaled 51.8 -> 115.6 MW"), identisch für S1 (gleiches ΔT, andere
Position). **136,8 MW > 115,6 MW** — die Knotenerzeuger ALLEIN (ohne ek_sb) können rechnerisch in JEDER Stunde,
einschließlich aller T_VL<95°C-Stunden, den vollen Lade-Leistungsdeckel des Tanks abdecken. Es gibt also KEINE
Kapazitätsgrenze, die eine vollständige Erzeugerdeckung verhindern würde — ob der Solver das in der Praxis so
dispatcht, ist eine Entscheidung, keine Kapazitätsfrage, und wird durch C2 (SB-S1-HK0, v9, läuft) direkt
beobachtbar sein (Nachheizwärme-KPI nach Erzeuger, Teil C Berichtsraster).
Status: belegt (Konfiguration, reale Messreihe) + vermutet/berechnet (Kapazitäts-Suffizienz-Argument, keine
Dispatch-Observation) — siehe v10-M1 für die Datenlücke.

---

## B2 — Szenario S3 im Modell v9 (Tank an j_man)

**Befund:** `scenarios.yaml` definiert S2 (j_man/j_12, ohne `hot_charging`) und S3 (dieselben Knoten, MIT
`hot_charging: true`) bereits als getrennte Szenario-IDs. Die A2-Analyse bestätigt, dass S2 exakt den
Standardfall (generischer Knotenbus) nutzt und damit unter E2 physikalisch inkonsistent ist; S3 nutzt die
Hot-Charging-Kopplung (`Qc == Q_hot`), die die Ladewärme exklusiv aus dem WP-Hot-Kanal nimmt — konsistent mit
E2s 95°C-Annahme.

**Umsetzung (Commit `b10c201`, Env-Schalter `CALION_LEGACY_S2_CHARGING`):** `run_single_scenario` bricht jetzt
mit einer erklärenden `ValueError` ab, wenn ein Szenario `tes_node == "S2"` (und kein `baseline`, kein
`hot_charging`) ohne den Override-Flag gestartet wird. S3 ist unverändert lauffähig. Verifiziert: SB-S2-HK0
bricht ab (erwartet), SB-S3-HK0 erreicht den Build normal (erwartet), SB-S2-HK0 mit
`CALION_LEGACY_S2_CHARGING=1` erreicht den Build ebenfalls normal (Override funktioniert).

**Konsistenzprüfung Hot-Charging ↔ E1/E2:** Aus dem Build-Log (`SB-S2-HK0`, bzw. identisch für S3, da E1/E2 vor
der S2/S3-Verzweigung greifen): `delta_T_scenario_k = t_store_max_c(95.0) - T_RL,ref(61.53) = 33,47 K`
(E2, reale Messreihe als T_RL,ref) — identisch für S2 und S3, da beide dieselbe ΔT-Injektion durchlaufen,
BEVOR die Lade-Kopplung entschieden wird. Die Hot-Charging-Kopplung selbst (`cop_charge_series_override`,
`T_charge_c = min(T_VL_max, t_store_max_c)`) verwendet ebenfalls die E1-Messreihe (`T_VL_max` kommt aus
`hk_stage["T_VL_max_c"]`, welches unter E1 aus der realen Reihe abgeleitet ist) — **keine Abweichung
gefunden**, S3 ist mit E1/E2 konsistent.
Status: belegt (Code + Build-Log-Zitat + Verifikationslauf)

---

## Zeitschätzung Teil C (vor Start, wie gefordert)

**Methode:** Verhältnis (Alt-Modell-Investitionslauf-Zeit ÷ Alt-Modell-PIN0-Zeit) aus der archivierten
`B4_konvergenz_provenienz.csv` (v7_final), angewendet auf die bekannte v9-PIN0-Zeit (aus C2, `REPORT_v9.md`).
Explizit eine GROBE Schätzung (Thread-Zahlen zwischen Alt-Lauf und v9-Lauf nicht identisch: Alt SB-S1
threads=2, Alt MM-S1 threads=4, beide v9-Läufe threads=16) — Status vermutet/geschätzt, nicht belegt.

| Netz | Alt PIN0 [s] | Alt S1 [s] | Verhältnis | v9 PIN0 [s] (C2, belegt) | **v9-Schätzung REF/S1 [h]** |
|---|---|---|---|---|---|
| SB | 13.805,65 | 62.635,57 | 4,537 | 27.626,65 | **≈ 34,8 h** (Budget 48h) |
| MM | 514,6 | 1.640,72 | 3,188 | 2.253,6 | **≈ 2,0 h** (Budget 4h) |

**Startplan (sequenziell, v9-M3):**

| Nr. | Lauf | geschätzte Dauer | geplanter Start | geschätztes Ende |
|---|---|---|---|---|
| C1 | SB-REF-HK0 | ≈ 25–35 h (etwas unter S1 geschätzt: kein TES-Sizing, nur WP/EK) | 2026-10-29 ~10:15 | ≈ 2026-10-30 ~12:00–21:00 |
| C2 | SB-S1-HK0 | ≈ 34,8 h | nach C1 | ≈ 36–40h nach C2-Start |
| C3a | MM-REF-HK0 | ≈ 1,5–2 h | nach C2 | + ~2h |
| C3b | MM-S1-HK0 | ≈ 2,0 h | nach C3a | + ~2h |

**Kritischer Pfad gesamt: grob 3–4,5 Tage Wandzeit** (SB-Anteil dominiert; MM-Anteil ist im Vergleich klein).
Alle vier Läufe: Warmstart vom jeweiligen PIN0-Dump (v9-C2) mit `CALION_SEED_FILL_ZERO=1`, Matched-Effort
(MIPFocus=3, Threads=16, Ziel-Gap 0,15%), gepinnt auf CPUs 0-15 (Koordination mit Peer-Job auf 16-31, wie in
v9-C2). Nach jedem fertigen Lauf: Zwischen-Commit mit Kennzahlen (wie gefordert).

---

## Meldepflichten v10

**v10-M1:** Die archivierte v7/v8-Investitions-Dispatchreihe (`output/paper2_runs/SB-S1-HK0`, sowie das
referenzierte `output/v7_final/`-Archiv) existiert nicht mehr auf der Platte — überschrieben durch spätere
Build-Tests unter derselben scenario_id. A2s Erzeuger-Deckungsschätzung musste daher auf Konfigurationsdaten
(Nennleistungen, hydraulischer Deckel) statt auf eine echte historische Dispatch-Beobachtung gestützt werden.
Die scenario-id-Überschreibungsgefahr ist bereits aus v9/C2 bekannt (dort: SB/MM-PIN0-Altbaseline), bleibt
aber ein wiederkehrendes Muster, das ein dediziertes Archivierungsschema (vor jedem `force_rerun=True`-Lauf
auf eine bekannte alte scenario_id) verdienen würde — nicht in diesem Auftrag umgesetzt (außerhalb des Scopes).

---

## C1 — Ergebnisse (SB-REF-HK0)

**Status/Gap/TAC:** `maxTimeLimit` (48h-Budget ausgeschöpft, nicht die 0,15%-Ziel-Gap — wie in der
Zeitschätzung oben als wahrscheinlichstes Ergebnis vermerkt). Gap am Ende **0,517%**. Solution count 10
(beste 10 Inkumbenten zwischen 21,9497 und 21,9576 Mio EUR, letzte Verbesserung spät im Lauf). Objektivwert
**21.949.652,47 EUR**. Laufzeit 174.052,3 s (≈ 48,35 h). n_vars 7.375.930, n_constraints 9.276.851 (fast
identisch zu PIN0: 7.349.659 / 9.162.968 — Δ nur durch die zusätzlichen WP/EK-Investitionsvariablen).

**Gebaut (WP/EK/TES):**

| Asset | Kapazität | Build |
|---|---|---|
| HP hp_sb | 11,9 MW | 1,0 (gebaut) |
| TES (Speicher) | 0,0 MWh / 0,0 MW | 0,0 (per Szenario-Override hart deaktiviert, wie vorgesehen) |

TES-Deaktivierung via `discrete_energies_mwh: [0]` wirkte wie in der Scenario-Definition erwartet — Geometrie
bestätigt `V=0 m³, h=0 m, E=0 MWh`. EK (p2h_existing) erscheint nicht in der Design-Extraktion als separat
investierbares Asset in diesem Lauf (nameplate-fixiert, siehe A2-Kapazitätsargument oben: 9,9 MW_el, nicht Teil
der Investitionsentscheidung in REF).

**Kostenvergleich vs PIN0 (SB-S0-HK0-PIN0, obj=23.314.348,08 EUR, gap 0,1455%):**

Δ Objektiv: **−1.364.695,61 EUR (−5,85%)** — reiner WP-Effekt ohne TES (das ist der "E5-Effekt", den C1 laut
Auftrag zeigen soll: Speicherwert-Referenz).

| Kostenzeile | PIN0 [EUR] | REF (C1) [EUR] | Δ [EUR] |
|---|---|---|---|
| Capex_cost | 0,0 | 1.240.995,1 | +1.240.995,1 |
| Activation_cost | 0,0 | 4.012,1 | +4.012,1 |
| Fuel_cost | 25.620.400,4 | 21.110.859,2 | −4.509.541,2 |
| Grid_energy_cost | 26.345,3 | 26.770,9 | +425,7 |
| Grid_sell_revenue | −11.345.675,0 | −8.771.829,3 | +2.573.845,7 |
| CO2_cost (brutto) | 6.754.021,3 | 5.638.093,8 | −1.115.927,4 |
| Demand_charge_cost | 38.237,0 | 41.840,4 | +3.603,4 |
| OM_fixed_cost | 1.547.000,0 | 1.582.689,7 | +35.689,7 |
| OM_variable_cost | 671.330,1 | 681.027,7 | +9.697,5 |
| **real_costs_total** | 23.311.659,06 | 21.554.459,59 | **−1.757.199,47** |

Mechanismus: Der WP-Zubau (11,9 MW, Jahresnutzung 48.886 MWh_th über die Leitung hkw_to_man, siehe unten)
ersetzt knapp 4,51 Mio EUR Brennstoffkosten und 1,12 Mio EUR CO2-Kosten (brutto), kostet aber 1,24 Mio EUR
Jahres-CAPEX und reduziert die KWK-Stromverkaufserlöse um 2,57 Mio EUR (weniger Kessel-/KWK-Fahrt → weniger
Kuppelstrom). Netto bleibt ein klarer Vorteil des WP-Zubaus allein (ohne TES) von knapp 1,36 Mio EUR/Jahr TAC.
Der Dump_cost (Modell-Aux-Term, 395.192,9 EUR) wurde separat geprüft und erklärt den Rest der Differenz
zwischen real_costs_total (−1.757.199,47 EUR Δ) und objective_total (−1.364.695,61 EUR Δ) vollständig
(objective_total = real_costs_total + Dump_cost, beide Läufe; alle übrigen model_aux_terms sind 0, inkl.
Pressure_slack_cost_EUR — SB hat keine j_13-Druckstation, die A1-Problematik betrifft nur MM).

**WP-Einspeisung via hkw_to_man:** Leitung führt in diesem Lauf ausschließlich Vorwärtsfluss (hkw → j_man),
**0 Stunden Rückfluss**. Summe 48.886,2 MWh_th/a, Peak 11,914 MW (≈ Nennleistung der gebauten WP). Das
bestätigt, dass die WP an j_man in REF rein lastdeckend arbeitet und nicht in Gegenrichtung ins hkw-Bündel
einspeist — plausibel für diese Topologie ohne TES-Pufferung.

**Bilanzschluss:** `[HEAT-BALANCE-AUDIT]` meldet Restsumme 0,001 MWh über 61.320 Knotenbilanzen (max. Einzel-
residuum 0,0000 MWh) → **schließt**. Diagnosekomponenten: ht_out=645.030, heatd=639.973,5, netzloss_full=
19.667,5, return=7.484, dump=79.038,6 MWh.

**Laufzeit/RAM:** 174.052,3 s (48,35 h) auf 16 gepinnten Threads (CPUs 16-31, Peer-Koordination "Slot B"),
NodefileStart=6 GB. Gemessener RAM-Peak während des Laufs ≈ 67,8 GB (peer-gemeldet und selbst verifiziert kurz
vor Lauf-Ende). Node-Explorationsrate deutlich langsamer als die Alt-Modell-Schätzung (76.037 Knoten in 48h vs.
die aus v7_final abgeleitete ≈35h-Erwartung) — die Bound blieb ab ca. Stunde 20 bei 21,836 Mio EUR stehen, die
Gap schloss danach nur noch über Inkumbenten-Heuristiken (10 Verbesserungen in den letzten ~28h). Für C2/C3
realistisch einplanen: ebenfalls Ausschöpfung des TimeLimits statt Erreichen der 0,15%-Ziel-Gap ist der
wahrscheinlichere Ausgang, nicht die Ausnahme.
