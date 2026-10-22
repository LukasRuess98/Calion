# REPORT — AC-Block (vor dem Schreiben): Rückgabe an den Dimensionierungs-Agenten (Stand 2026-10-22, 09:40)

Antwort auf den Auftrag „AC) VOR DEM SCHREIBEN“ (AC1 Leistung bepreisen, AC2 Geometrie, AC3 Protokoll-Lücken).
Arbeitsbranch: `Loc_TES_Study_P2`, Commits `812c460`, `719ca19`, `342e877` (nicht gepusht).
Details und Belege: `docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md`, §4cq (Ende der Datei).
Kennzeichnung: **belegt** = aus Datei/Log gelesen, **berechnet** = aus belegten Werten abgeleitet, **offen** = Lauf noch nicht abgeschlossen.

---

## 1. Kernaussage (bitte zuerst lesen)

**Die bisherige Kernaussage „SB-Speicher hat positiven Wert, 165–230 k€/a“ gilt nur, solange Lade-/Entladeleistung kostenlos ist.** Mit dem aus der Primärquelle belegten Leistungskostenterm (Basis 280.274 €/MW) baut der Optimierer im SB-Basisfall **keinen Speicher** (`geometry.csv`: build = 0, V_TES = 0, cap_power = 0). **belegt**

Zusätzlich war die bisherige Wertdefinition unscharf: PIN0 bedeutet „keine Investition in Wärmepumpe, Elektrokessel und Speicher“, das freie Modell investiert in alle drei. Die Intervalle PIN0 gegen frei sind daher der Wert des **Pakets**, nicht des Speichers allein. **belegt** (Details unter 3.)

## 2. AC1 — Leistung bepreisen

### AC1a — Befund (belegt)
- `cap_power` ist eine freie Variable mit der einzigen Restriktion `cap_power ≤ power_to_energy_ratio · E_max` (`calion/models/blocks/geometric_storage.py`). Sie steht in **keinem** Kostenterm.
- E/P = 4 h stammt aus `power_to_energy_ratio: 0.25` (Netzwerk-YAMLs, Default im Code). Eine Begründung ist nirgends dokumentiert. Es ist ein Default.
- SB-S1 (c0×1,0, alt): E = 438 MWh, cap_power = 109,5 MW. Aus `dispatch_hourly.csv`: Ladespitze 109,5 MW (auch das 99-%-Quantil), Entladespitze 81,1 MW, etwa 70 Vollzyklen/a. Die Leistung wird also tatsächlich ausgefahren.
- Primärquelle (DEA/Energinet, *Technology Data – Energy Storage*, v0009, Kap. 141, aus dem PDF gelesen): Investition nur energiebezogen (3,0 M€₂₀₁₅/GWh, 70 % Ausrüstung / 30 % Installation), **kein Leistungsterm**; Referenzeinheit 175 MWh bei 2,9 MW, das entspricht E/P ≈ 60 h. Das Modell rechnet mit 4 h, dem 15-Fachen.

### AC1b — Leistungsterm (belegt, Primärquelle)
- Quelle: DEA/Energinet, *Technology Data for Energy Transport*, Version 8 (Dez. 2025), Excel-Blatt „3.1 DH transmission“, Kostenjahr 2025, direkt gelesen:
  Wärmeübertragerstation 140.161,8 €/MW (77.089 – 168.194), Pumpstation 127.473,2 €/MW (70.110 – 152.968), Leitung 63,19 €/MW/m (50,75 – 75,00).
- Zusammensetzung: **Basis** 280.274 €/MW (Pumpstation + WÜ-Station + 200 m Leitung), **niedrig** 75.185 €/MW (nur Pumpstation, untere Werte, 100 m Leitung), **hoch** 358.663 €/MW (obere Werte + 500 m Leitung). Nur die Leitungslängen sind eine Annahme von mir.
- Umsetzung: `power_capex_eur_per_mw · cap_power` im Tank-CAPEX, annuitisiert und mit O&M wie der Tank (30 a, 0,5 %). Env `CALION_TES_POWER_CAPEX` (0 = Altmodell).
- Offene Fachfrage: Ob der atmosphärische SB-Tank bei 16 bar Netzdruck ohne Wärmeübertrager direkt anschließbar ist, kann ich nicht aus Quellen entscheiden. Deshalb Spanne statt Punktwert (siehe AC1c, niedrige Variante).

### AC1c — SB-S1 neu gerechnet (Zielgap 0,15 %, PIN0 gemeinsam)
PIN0 bleibt gültig: Mit deaktiviertem TES berühren weder Leistungsterm noch Höhenkappe das Modell. UB(PIN0) = 23.370.804,48 €, Gap 0,1436 %.

| Lauf | Ergebnis |
|---|---|
| c0×1,0, Basis 280.274 €/MW (**P1, fertig**) | Zeitlimit 48 h, **obj 23.317.347 €, Gap 0,182 %, Gurobi-Log „Solution count 10“, build = 0** |
| c0×1,5, Basis (P2) | **nicht gerechnet, ans Ende der Warteschlange gestellt.** Monotonie: höheres c0 macht nur Lösungen mit Speicher teurer; wo bei ×1,0 nichts gebaut wird, wird bei ×1,5 erst recht nichts gebaut. Lauf bleibt dennoch in der Queue (Ihr Auftrag). |
| c0×1,0, niedrig 75.185 €/MW (P3) | **offen**, läuft, Stand: Gap 0,32 %, Inkumbent 23,321 Mio. € (noch im Bereich der speicherfreien Lösungen) |

Wertintervalle (Y1-Methodik, Gap-bewusst):
- Paketwert HP/EK gegen PIN0 bei bepreister Leistung: **[19.888; 95.933] €/a** (berechnet)
- reiner Speicherwert bei bepreister Leistung: **[0; ≈ 42.000] €/a**, der Inkumbent selbst: 0 (berechnet; Referenz vorerst Proxy, siehe 3.)

### AC1d — E/P 4 h / 8 h / 12 h
**offen** (Altmodell mit kostenloser Leistung, Läufe in der Warteschlange). Der Befund zur tatsächlichen Leistungsnutzung steht schon unter AC1a (Ladespitze 109,5 MW bei E/P = 4 h).

## 3. Wichtige Definitionskorrektur (nicht Teil Ihres Auftrags, aber für das Paper nötig)

- **Beleg:** SB-S2 (Speicher am Wärmepumpenknoten) baut keinen Speicher, aber eine 1,8-MW-Wärmepumpe: obj 23.318.968,91 €, Gap 0,187 % (gültiger PIN0-Start, Solution count 10). Das sind ≈ 52 k€/a **allein aus der Wärmepumpe** gegenüber PIN0. SB-S3 gleich: 23.316.918,73 €, Gap 0,177 %, build = 0.
- Die frühere S2/S3-Zahl 23.384.317,87 € war ein **abgelehnter S1-Warmstart** („User MIP start violates constraint …“): S1 und S2 haben unterschiedliche Tankknoten, der S1-Start ist dort unzulässig.
- **Folge:** reiner Speicherwert (Altmodell, Leistung gratis, c0×1,0) **[103.592; 176.528] €/a** statt „165–230 k€/a“; die genannten 165–230 k€/a sind der **Paketwert**.
- `docs/paper_2/submission_pack/02_tables/tab_Z5b_package_vs_storage_only.csv` zeigt beide Spalten. Der reine Speicherwert hat vorerst eine **Proxy-Referenz** (SB-S3 bzw. MM-S2, Speicher erlaubt, aber nicht gebaut). Der saubere Referenzlauf `ac3_s0free_notes` (SB-S0-HK0, TES aus, HP/EK frei, PIN0-Start) steht kurz vor der 0,15 %-Marke; das Skript nimmt ihn danach automatisch (`python scripts/paper_2/z5_rebuild_table.py`).
- Die Tarif-/Preisspreizungs-Sensitivitäten stehen nur mit Paketwert in der Tabelle: Für den reinen Speicherwert bräuchte jeder Fall einen eigenen speicherfreien Lauf (nicht gerechnet).

## 4. AC2 — Geometrie

- **Befund (belegt):** Höhe ist keine Modellvariable, sondern wurde aus V und H/D nachträglich berechnet. SB-S1: V = 30.379 m³, H/D = 2 → **h = 53,68 m → 6,131 bar**, über dem dokumentierten Auslegungsdruck 5,5 bar (≙ 47,1 m) und der Reuter-West-Referenz (45 m). Außerdem wurde h bisher für das gesamte Volumen als **ein** Behälter gerechnet.
- **Umsetzung:** Höhenkappe `h_max_m = 45` begrenzt das Volumen eines Behälters auf π·h³/(4·H/D²) (H/D 2: 17.892 m³; 1,5: 31.809 m³; 1: 71.568 m³ → dann greift die 50.000-m³-Grenze), größere Speicher als N gleiche Behälter mit Kosten je Behälter. Aktive Assertion: Fußdruck bei 45 m (5,30 bar) ≤ 5,5 bar. `geometry.csv` meldet Höhe/Druck je Behälter, `n_tanks`, `r_hd`.
- **Analytisch (berechnet, `output/_ac/analysis/ac2_geometry_rung_table.csv`):** Der 438-MWh-Tank passt bei H/D ≤ 1,5 in einen Behälter (H/D 1,5: 44,3 m; H/D 1: 33,8 m, 4,24 bar), bei H/D = 2 braucht er zwei Behälter (je 42,6 m): Investition 5,44 → 6,70 M€ (+23 %), annualisiert etwa +88 k€/a, rund 40–50 % des Altwerts. **Die Geometrie bewegt die Kosten also deutlich.**
- **Läufe H/D 2 / 1,5 / 1 mit 45-m-Kappe:** **offen**, im Altmodell (Leistung gratis), weil nur dort der Speicher überhaupt gebaut wird.
- **Limitation:** Stratifikationseffizienz η_strat = 0,85 ist unabhängig von H/D modelliert (kleineres H/D hätte real schlechtere Schichtung).

## 5. AC3 — Protokoll-Lücken

| Punkt | Stand |
|---|---|
| SB-S2, SB-S3 neu | **fertig** (siehe 3.): beide build = 0, 8-h-Limit, Gap 0,187 % bzw. 0,177 %. Die Trennung UB(S1) < LB(S2) bleibt gültig und ist jetzt sogar enger: UB(S1) = 23,172 Mio. €, LB(S2) ≈ 23,275 Mio. €. |
| SB-MONTHLY (frei) neu | **offen**, in der Warteschlange (Altmodell, Start von PIN0-MONTHLY). Der bisherige Lauf ist nachweislich der Warmstart (obj identisch auf 10 Stellen, Log-Solution-count 1). |
| Z4-Bilanzfix auf S2/S3 | **fertig:** SB-S2/S3 Closure 3,305 % → 0,269 % (bestanden), MM-S2/S3 25,57 % → 1,959 % (bestanden). Der Code-Fix liegt in `Loc_TES_Study_P2` (auf `main` fehlte er: Branch-Stand, kein Verlust). |
| c0×0,5 und ×0,7 | **fertig** (Altmodell, Warmstart von v7_final/S1): ×0,5 obj 22.981.415,31 €, Gap 0,228 %, Solution count 1; ×0,7 obj 23.057.656,99 €, Gap 0,153 %. Beide bauen **denselben** Speicher wie c0×1,0 (30.379,4 m³). Einschränkung: Log-Solution-count 1 bei ×0,5 heißt, die Größe wurde nicht neu gesucht, also gültige obere Schranke, kein Beleg der optimalen Größe. |
| MODEL_AND_DOE_CONTROL.md ab §4ck | **fertig:** §4ck–§4cp waren in `Loc_TES_Study_P2` bereits vorhanden, §4cq (AC-Block) neu. |
| T3–T5, F2–F9 | **weiter veraltet** (Altmodell: Leistung gratis, keine Höhenkappe). Neu erzeugt sind nur F_TES1–F_TES4 und die Z5b-Tabelle. `tab_T_TES_value_summary.tex` ist noch nicht umgestellt. |

## 6. Methodische Warnungen

1. **`meta.json`/`solution_count` ist unzuverlässig** (steht überall auf 1). Belastbar ist nur die Zeile „Solution count“ im Gurobi-Log (`<OUT_BASE>/../logs/gurobi_<id>.log`). Das Z5-Skript liest sie jetzt von dort.
2. Die Aussage zu den Läufen mit Log-Solution-count 1 (c0×1,3, ×1,5, ×0,5, Tarifvarianten mit gleicher Größe) bleibt: gültige obere Schranke, nicht die neu gesuchte Größe.
3. Die Altmodell-Zahlen sind mit `CALION_TES_POWER_CAPEX=0 CALION_TES_HMAX=0` reproduzierbar. Ohne diese Env-Variablen gilt jetzt das neue Modell (`storage_geometry.yaml`: 280.274 €/MW, 45 m).

## 7. Was ich vom Agenten brauche (Entscheidungen)

1. Soll die Arbeit die Aussage als **Spanne** über die Leistungskosten formulieren (75 / 280 / 359 k€/MW), solange die Direktanbindungsfrage fachlich offen ist? Meine Empfehlung: ja.
2. Soll `tab_T_TES_value_summary.tex` auf die zwei Definitionen (Paketwert / reiner Speicherwert) umgestellt werden? Meine Empfehlung: ja, nach Abschluss von P3 und der Referenz.
3. Sollen die Tarif- und Preisspreizungs-Fälle je einen eigenen speicherfreien Lauf bekommen (rund 8 SB-Läufe, jeweils bis zu 48 h)? Ohne sie bleibt die Spalte „reiner Speicherwert“ für diese Fälle leer.

## 8. Dateien

- Bericht/Doku: `docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md` (§4cq)
- Tabelle: `docs/paper_2/submission_pack/02_tables/tab_Z5b_package_vs_storage_only.csv`
- Abbildungen: `docs/paper_2/submission_pack/01_figures/F_TES1…F_TES4` (SVG getrackt, PNG/PDF gitignored)
- Läufe: `output/_ac/<tag>/` (eigene Pfade), `output/_s2/` (Parallel-Session)
- Code: `calion/models/blocks/geometric_storage.py`, `calion/models/component_assembler.py`, `configs/paper_2/storage_geometry.yaml`, `scripts/paper_2/scenario_runner.py`, `scripts/paper_2/ac_run.sh`, `scripts/paper_2/ac_scheduler.py`, `scripts/paper_2/z5_rebuild_table.py`
