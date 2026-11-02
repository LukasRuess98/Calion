# REPORT v10 — Prüfpunkte + Kernlaufsatz Modell v9

Antwort auf `docs/paper_2/agent_prompts/v10_Kernlaufsatz.md`. Basis: Tag `p2-v9-model`, Branch `p2_v9_consolidation`.
Status: **Teil A, B und C abgeschlossen.** Alle vier vorgeschriebenen Läufe (C1-C3b) fertig, siehe
Gesamtfazit am Ende des Dokuments. Gemäß Auftrag: STOPP nach Teil C.

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

---

## C2 — Ergebnisse (SB-S1-HK0)

**Status/Gap/TAC:** `maxTimeLimit` (48h-Budget ausgeschöpft). Gap am Ende **2,121%** (schlechter als C1,
Bound stagnierte früher und stärker — 81.112 Knoten/2.551.375 Simplex-Iterationen in 172.857,7 s). Solution
count 10. Objektivwert **22.127.974,67 EUR**. Laufzeit 174.098,8 s (≈ 48,36 h). Warmstart korrekt von
`SB-S0-HK0-PIN0` (nicht von C1/REF — wie vorgeschrieben, keine Transplantation zwischen TES-Standorten).

**Gebaut (WP/EK/TES):**

| Asset | Kapazität | Build |
|---|---|---|
| HP hp_sb | 13,8 MW | 1,0 (gebaut; größer als in REF: 11,9 MW — TES ermöglicht/verlangt mehr WP-Leistung) |
| TES tes_sb | V=4.538,3 m³, h=23,5 m, E=146,0 MWh, p=3,25 bar, Leistung=38,8 MW | 1,0 (gebaut) |

**Speicherbetrieb:** SOC-Band 7,3–146,0 MWh (nie vollständig leer, min ≈5% der Kapazität). Ladesumme
21.079,1 MWh/a, Entladesumme 20.023,1 MWh/a (Rundtrip-Verlust ≈5%, plausibel). Peak-Lade-/Entladeleistung
je 38,8 MW (symmetrisch, = cap_power). **≈137 Vollzyklen/Jahr** (Entladesumme/E_max) — kurzzyklischer
Tages-/Mehrtagespuffer an der Zentrale (j_hkw), keine Saisonspeicherung; passt zur kleinen Kapazität bei
vergleichsweise hoher Leistung.

**WP-Einspeisung via hkw_to_man:** wie in C1 ausschließlich Vorwärtsfluss, **0 Stunden Rückfluss**. Summe
52.628,8 MWh_th/a, Peak 13,791 MW (≈ Nennleistung der gebauten WP, etwas höher als in REF).

**Kostenvergleich vs PIN0 und vs REF:**

Δ Objektiv vs PIN0: **−1.186.373,41 EUR (−5,09%)**. Δ Objektiv vs REF: **+178.322,20 EUR (+0,81%)** — TES
zusätzlich zur WP macht das Ergebnis in diesem (noch nicht konvergierten) Lauf nominal leicht *teurer*, nicht
günstiger.

| Kostenzeile | PIN0 [EUR] | REF (C1) [EUR] | S1 (C2) [EUR] | ΔS1−PIN0 | ΔS1−REF |
|---|---|---|---|---|---|
| Capex_cost | 0 | 1.240.995 | 1.600.924 | +1.600.924 | +359.929 |
| Activation_cost | 0 | 4.012 | 4.012 | +4.012 | +0 |
| Fuel_cost | 25.620.400 | 21.110.859 | 20.717.115 | −4.903.286 | −393.744 |
| Grid_energy_cost | 26.345 | 26.771 | 65.157 | +38.812 | +38.386 |
| Grid_sell_revenue | −11.345.675 | −8.771.829 | −8.994.913 | +2.350.762 | −223.083 |
| CO2_cost (brutto) | 6.754.021 | 5.638.094 | 5.562.224 | −1.191.797 | −75.870 |
| Demand_charge_cost | 38.237 | 41.840 | 376.609 | +338.372 | **+334.769** |
| OM_fixed_cost | 1.547.000 | 1.582.690 | 1.600.965 | +53.965 | +18.276 |
| OM_variable_cost | 671.330 | 681.028 | 683.339 | +12.009 | +2.312 |
| **real_costs_total** | 23.311.659 | 21.554.460 | 21.615.433 | **−1.696.226** | **+60.973** |

**Mechanismus vs REF:** Der TES-Zubau senkt Fuel (−393.744 EUR) und CO2 (−75.870 EUR) weiter, aber treibt
`Demand_charge_cost_EUR` (Netzentgelt Lastspitze) um **+334.769 EUR** nach oben — die größere WP (13,8 statt
11,9 MW) plus die TES-Ladeleistung (bis 38,8 MW) erzeugen eine neue, höhere Strom-Lastspitze beim Laden. Dazu
kommt ein verschlechterter KWK-Stromerlös (−223.083 EUR) und mehr Netzstrombezug (+38.386 EUR). Netto kippt
das knapp ins Minus (vs REF).

**Wichtiger Vorbehalt — Gap-Band vs Interpretierbarkeit:** Die ΔS1−REF von +178.322 EUR (+0,81% von S1s
Objektiv) ist **kleiner als die Summe der beiden Optimality-Gaps** (REF 0,517% ≈ ±113.000 EUR; S1 2,121% ≈
±469.000 EUR — S1s Gap-Band allein ist bereits >2,5× so groß wie die beobachtete Differenz). Die Aussage
"TES zusätzlich zur WP ist unter v9/E3b teurer als WP allein" ist bei diesem Konvergenzstand **nicht
belastbar** — das echte Vorzeichen bleibt offen, bis beide Läufe deutlich näher an ihre Ziel-Gap (0,15%)
kommen. Festzuhalten ist nur der Mechanismus (Demand-Charge-Treiber), nicht das Netto-Vorzeichen.

**Neuer Befund (Meldepflicht v10-M2) — Objective_residual_EUR in cost_breakdown.json:** Der Lauf löst eine
im Code bereits vorhandene Tripwire aus: `[COST-BREAKDOWN] Objective_residual_EUR = 82.204,43 EUR (> 1 EUR
Toleranz)` — die 17 benannten Objektivterme reproduzieren `model.obj` nicht vollständig (0,37% des
Objektivwerts fehlt, Quelle nicht identifiziert). In C1/REF war dieser Residualterm exakt 0 (TES dort über
`discrete_energies_mwh:[0]` hart deaktiviert); er taucht hier zum ersten Mal auf, sobald TES im Preheat-Modus
tatsächlich gebaut und zyklisch betrieben wird — Verdacht liegt nahe bei einem TES-Kostenterm (degressive
Kostenkurve `_cost_k[k]*ysel[k]`, geometric_storage.py ~L400-421) oder einer bislang nicht erfassten
Kopplungs-/Tie-Break-Größe im Preheat-Pfad, aber **nicht verifiziert** — eine echte Ursachenklärung wäre ein
Code-Eingriff außerhalb des für diesen Auftrag autorisierten Scopes (nur B2 war freigegeben) und wurde daher
NICHT vorgenommen. Folge für diesen Report: `objective_total_EUR` (roher MILP-Wert) ist weiterhin autoritativ
und wird oben für alle TAC-Vergleiche verwendet; die Kostenzeilen-Tabelle (`real_costs_EUR`) für S1 ist um
82.204,43 EUR zu niedrig, Quelle unbekannt. Wird in C3 (MM) gegengeprüft, ob derselbe Effekt auftritt.

**Bilanzschluss:** `[HEAT-BALANCE-AUDIT]` meldet Restsumme 0,001 MWh über 61.320 Knotenbilanzen (max.
0,0000 MWh) → **schließt** (physikalisch unabhängig vom Kosten-Residuum oben). Diagnosekomponenten:
ht_out=665.717, heatd=639.973,5, netzloss_full=19.667,5, return=7.484, dump=86.067,4 MWh.

**Laufzeit/RAM:** 174.098,8 s (48,36 h), 16 gepinnte Threads (CPUs 16-31). RAM zuletzt vor Lauf-Ende bei
≈52 GB gemessen (deutlich unter dem 96-GB-Eigenbudget). NodefileStart=6 GB.

---

## C3a — Ergebnisse (MM-REF-HK0)

**Status/Gap/TAC:** `optimal` — **Ziel-Gap erreicht** (0,1015% < 0,15%-Vorgabe), deutlich schneller als SB.
Solution count 1. Objektivwert **419.235,11 EUR**. Laufzeit 8.327,1 s (≈ 2,31 h, innerhalb des 4h-Budgets).
n_vars 4.599.010, n_constraints 4.940.651.

**Gebaut (WP/EK/TES):** **HP hp_main: capacity=0,0 MW, build=0,0 — keine WP gebaut**, obwohl in REF frei
erlaubt (anders als SB-REF-HK0, wo die WP gebaut wurde). Unter v9/HK0-Ökonomie lohnt sich der WP-Zubau in
MM offenbar nicht, selbst ohne TES-Restriktion. TES: wie vorgesehen hart auf 0 (`V=0 m³, E=0 MWh`). Keine
WP-Einspeisung zu berichten (hp_main nicht gebaut → kein Pendant zu "hkw_to_man" aktiv).

**Kostenvergleich vs PIN0 (MM-S0-HK0-PIN0, obj=419.817,29 EUR, gap 0,1479%):**

Δ Objektiv: **−582,18 EUR (−0,14%)** — bei identischem Nicht-Zubau (kein HP in beiden Läufen) ist dies
**kein realer Investitionseffekt**, sondern Lösungs-Rauschen zwischen zwei nahe-optimalen MILP-Läufen mit
unterschiedlichem Warmstart. Aufschlüsselung bestätigt das:

| Kostenzeile | PIN0 [EUR] | REF (C3a) [EUR] | Δ [EUR] |
|---|---|---|---|
| Capex_cost | 0,0 | 1.127,0 | +1.127,0 |
| Fuel_cost | 287.839,1 | 285.273,3 | −2.565,8 |
| CO2_cost (brutto) | 33.476,5 | 32.627,8 | −848,8 |
| Demand_charge_cost | 1.541,5 | 1.870,9 | +329,4 |
| **real_costs_total** | 408.363,23 | 408.420,80 | **+57,58** |
| **Pressure_slack_cost_EUR** (Aux, A1) | **11.379,68** | **10.744,28** | **−635,41** |

**Beantwortung der A1(c)-Offenlegung:** Die reale Kostensumme (`real_costs_total`) steigt in REF sogar
leicht (+57,58 EUR) — die gesamte scheinbare TAC-Verbesserung (−582,18 EUR) kommt aus einer Verschiebung
von `Pressure_slack_cost_EUR` (−635,41 EUR, ≈6% des eigenen Werts), die zwischen zwei strukturell
identischen (kein WP-Zubau) MILP-Läufen allein durch unterschiedliche Warmstart-Pfade zu leicht anderen
bindenden Stunden am j_13-Druckslack führt. **Schlussfolgerung für C3b:** Verschiebungen von
`Pressure_slack_cost_EUR` in der Größenordnung von ein paar hundert EUR zwischen MM-Läufen sind als
Lösungs-Rauschen zu werten, nicht als Signal — erst eine Änderung, die diese Hunderte-EUR-Bandbreite klar
übersteigt, ist bei MM-S1-HK0 vs MM-REF-HK0 als realer Effekt interpretierbar.

**Bilanzschluss:** `[HEAT-BALANCE-AUDIT]` Restsumme 0,000 MWh über 17.520 Knotenbilanzen → **schließt**.
Kein `Objective_residual_EUR`-Befund (Residual ≈0 in beiden Läufen) — das v10-M2-Phänomen aus C2 tritt hier
NICHT auf (passend zur dortigen Vermutung: tritt nur bei tatsächlich gebautem/zyklisch betriebenem TES im
Preheat-Modus auf; hier ist TES hart deaktiviert).

**Laufzeit/RAM:** 8.327,1 s (2,31 h), 16 gepinnte Threads (CPUs 16-31), NodefileStart=6 GB. RAM nicht
separat gemessen (Lauf beendete sich vor der nächsten geplanten Messung).

---

## C3b — Ergebnisse (MM-S1-HK0) — letzter Lauf der Kampagne

**Status/Gap/TAC:** `optimal` — **Ziel-Gap erreicht** (0,1497% < 0,15%, knapp). Solution count 1.
Objektivwert **419.368,69 EUR**. Laufzeit 7.946,7 s (≈ 2,21 h, innerhalb des 4h-Budgets). Warmstart korrekt
von `MM-S0-HK0-PIN0` (nicht von C3a/REF).

**Gebaut (WP/EK/TES):** **Beides null** — HP hp_main: capacity=0,0 MW, build=0,0; Storage: capacity=0,0 MWh,
power=0,0 MW, build=0,0. Obwohl TES hier (anders als in C3a) frei erlaubt war (`tes_node: "S1"`, TES an j_9),
entscheidet sich das Modell für **keinen Zubau — weder WP noch TES**. Das ist dasselbe Nicht-Investitions-
Ergebnis wie in C3a, nur jetzt mit TES-Option tatsächlich verfügbar statt hart gesperrt. Keine WP-Einspeisung
zu berichten (kein hp_main gebaut); keine TES-Betriebsdetails zu berichten (TES nicht gebaut, keine
Lade/Entlade-Zyklen).

**Kostenvergleich vs PIN0 und vs REF (C3a):**

Δ Objektiv vs PIN0: −448,60 EUR (−0,11%). Δ Objektiv vs REF: **+133,58 EUR (+0,03%)** — beide Größen liegen
innerhalb der in C3a etablierten Rausch-Bandbreite (dort: −635,41 EUR Pressure-Slack-Verschiebung zwischen
zwei strukturell identischen Nicht-Zubau-Läufen). Mit Δ(S1-REF)=+133,58 EUR ist diese Differenz hier sogar
noch kleiner als die C3a-Bandbreite selbst — **kein belastbares Signal, weder für noch gegen TES an j_9**,
weil das Modell TES an dieser Stelle schlicht nicht baut.

| Kostenzeile | PIN0 [EUR] | REF (C3a) [EUR] | S1 (C3b) [EUR] | ΔS1−REF |
|---|---|---|---|---|
| Capex_cost | 0,0 | 1.127,0 | 1.127,0 | +0,0 |
| Activation_cost | 0,0 | 1.604,9 | 1.604,9 | +0,0 |
| Fuel_cost | 287.839,1 | 285.273,3 | 285.143,6 | −129,6 |
| Grid_energy_cost | 1.338,9 | 1.461,2 | 1.490,7 | +29,5 |
| Grid_sell_revenue | −11.371,0 | −11.188,1 | −11.165,4 | +22,7 |
| CO2_cost (brutto) | 33.476,5 | 32.627,8 | 32.609,4 | −18,4 |
| Demand_charge_cost | 1.541,5 | 1.870,9 | 2.120,4 | +249,5 |
| OM_fixed_cost | 76.000,0 | 76.093,6 | 76.093,6 | +0,0 |
| OM_variable_cost | 19.538,2 | 19.550,3 | 19.544,9 | −5,3 |
| **real_costs_total** | 408.363,23 | 408.420,80 | 408.569,23 | +148,43 |
| Pressure_slack_cost_EUR (Aux) | 11.379,68 | 10.744,28 | 10.729,53 | −14,74 |

(Capex_cost/Activation_cost sind in REF und S1 identisch — ein kleiner, vom WP/TES-Zubau unabhängiger
Fixanteil, vermutlich ein anderes, in beiden Läufen gleich gebautes Asset (z. B. EK), das `design_helpers`
hier nicht separat protokolliert; für den TES-Wertvergleich irrelevant, da er sich exakt heraushebt.)

**Fazit MM (C3a+C3b zusammen):** Unter v9/HK0-Ökonomie investiert MM **in keinem der beiden Szenarien** in
WP oder TES — weder wenn nur WP erlaubt ist (C3a) noch wenn zusätzlich TES an j_9 erlaubt ist (C3b). Beide
Läufe konvergieren auf praktisch denselben ("Nichts bauen")-Betriebspunkt, mit Abweichungen, die vollständig
durch Lösungs-Rauschen (Warmstart-abhängige Pressure-Slack-Stundenverteilung) erklärt sind. Dies steht im
Kontrast zu Stadtbach (C1/C2), wo sowohl WP als auch TES tatsächlich gebaut werden. Eine Ursachenklärung
(warum MM unter HK0 nicht investiert — A1s Hydraulik-Befund, andere Lastcharakteristik, oder schlicht ein
für MM ungünstigeres WP/TES-Kostenverhältnis am gewählten Standort) ist **außerhalb des Scopes dieses
Auftrags** (nur Teil-C-Läufe, kein zusätzlicher Analyse-Auftrag) und wird hier nur als Befund festgehalten.

**Bilanzschluss:** `[HEAT-BALANCE-AUDIT]` Restsumme 0,000 MWh über 17.520 Knotenbilanzen → **schließt**.
Kein v10-M2-Residual-Befund (Objective_residual_EUR ≈0) — konsistent mit der C2-Vermutung, dass dieser
Effekt an ein tatsächlich gebautes, zyklisch betriebenes Preheat-TES gebunden ist (hier: TES nicht gebaut).

**Laufzeit/RAM:** 7.946,7 s (2,21 h), 16 gepinnte Threads (CPUs 16-31), NodefileStart=6 GB.

---

## Gesamtfazit Teil C (alle vier Läufe)

| Lauf | Status | Gap | Obj [EUR] | gebaut WP | gebaut TES | Δ vs PIN0 | Δ vs REF |
|---|---|---|---|---|---|---|---|
| C1 SB-REF-HK0 | maxTimeLimit | 0,517% | 21.949.652 | 11,9 MW | — (gesperrt) | −1.364.696 (−5,85%) | — |
| C2 SB-S1-HK0 | maxTimeLimit | 2,121% | 22.127.975 | 13,8 MW | 146,0 MWh/38,8 MW | −1.186.373 (−5,09%) | +178.322 (+0,81%, **nicht belastbar**, Gap-Band größer) |
| C3a MM-REF-HK0 | **optimal** | 0,1015% | 419.235 | 0 (nicht gebaut) | — (gesperrt) | −582 (−0,14%, Rauschen) | — |
| C3b MM-S1-HK0 | **optimal** | 0,1497% | 419.369 | 0 (nicht gebaut) | 0 (nicht gebaut) | −449 (−0,11%, Rauschen) | +134 (+0,03%, Rauschen) |

**Kernaussagen:**
1. **Stadtbach investiert** (WP in beiden Läufen, TES zusätzlich in S1); **Memmingen investiert in keinem
   der beiden v10-Läufe** (weder WP noch TES) — ein klarer, struktureller Unterschied zwischen den beiden
   Netzen unter v9/HK0-Ökonomie, nicht weiter ursachengeklärt (außerhalb des Scopes).
2. Für SB ist der reine WP-Wert (C1 vs PIN0) gut belegt (−5,85%, Gap 0,517%, deutlich innerhalb Rauschband).
   Der zusätzliche TES-Wert (C2 vs C1) ist **nicht belastbar** — C2s Gap (2,121%) ist größer als die
   beobachtete Differenz selbst; eine Aussage zum Vorzeichen des TES-Zusatzwerts an j_hkw erfordert einen
   weiteren, besser konvergierten Lauf (außerhalb des Scopes dieses Auftrags).
3. Für MM sind beide Läufe gut konvergiert (Ziel-Gap erreicht), das Ergebnis ist aber ein doppeltes
   Negativ-Finding: kein WP-, kein TES-Zubau unter den gegebenen Randbedingungen (Standort j_12/j_9, HK0).
4. **v10-M2** (Objective_residual_EUR, 82.204 EUR in C2) bleibt ungeklärt, tritt nur bei tatsächlich
   gebautem/zyklisch betriebenem Preheat-TES auf (C2); C1/C3a/C3b zeigen das Artefakt nicht. Für alle TAC-
   Vergleiche wurde durchgehend `objective_total_EUR` (roher MILP-Wert) verwendet, nicht die möglicherweise
   unvollständige `real_costs_EUR`-Zerlegung.
5. **v10-M1** (verlorene v7-S1-Dispatchreihe) bleibt wie in A2 dokumentiert ein offener Daten-Befund, ohne
   Auswirkung auf die hier gelieferten Teil-C-Ergebnisse (die stützen sich nicht auf die verlorene Reihe).

**Resourcen/Koordination:** alle vier Läufe liefen sequenziell (v9-M3-Lehre: kein Parallelbau), gepinnt auf
CPUs 16-31 ("Slot B"), koordiniert mit der Peer-Session (eigene Jobs auf "Slot A", 0-15). RAM-Eigenverbrauch
blieb durchgehend unter dem 96-GB-Eigenbudget (Peak beobachtet: ≈68 GB während C1/C2-Übergang).

**STOPP nach Teil C — wie im Auftrag vorgeschrieben. Keine weitere Arbeit ohne neue explizite Anweisung.**
