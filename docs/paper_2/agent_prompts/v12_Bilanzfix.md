# AGENT-AUFTRAG Paper 2 — v12.3 „Bilanzfix + Ergebniskampagne“ (2026-11-06, ersetzt v12, v12.1, v12.2)

Zuerst: Lege diesen Auftrag unverändert als `docs/paper_2/agent_prompts/v12_Bilanzfix.md` ab (v12 überschreiben).

Antwort auf `REPORT_v11.md` (p2_v9_consolidation@7aa6a49) und auf deine Kritik an v12 (alle fünf Punkte übernommen, siehe Änderungsliste
am Ende). Branch: `p2_v9_consolidation`. Report: `docs/paper_2/agent_reports/v12/REPORT_v12.md`, docs auf `main` spiegeln.
Freigegeben: alle [x]-Punkte ohne Rückfrage. Teil D startet selbstständig, wenn D0 erfüllt ist; sonst STOPP und Report.
Beweisregel: **belegt** (Datei:Zeile, Dump-Wert), **berechnet** (Rechenweg), **vermutet**.

## Rahmen des Papers (bindend)

Verschachteltes Schema: äußere Schleife fixierte Auslegungen aus einem Raster, innere Schleife Jahresbetrieb. Keine simultane
Optimierung von Heizkurve, Größe und Standort.
- **RQ1 Temperatur/Geometrie:** Wie bestimmt das Vorlauf-/Rücklaufniveau (HK0 vs. HK2) Speicher-ΔT, Entlademodus
  (direkt vs. Vorwärmung) und damit Wert und kostenoptimale Größe?
- **RQ2 Topologie:** Speicher am Erzeugerhub (SB j_hkw / MM j_9) oder an der WP/Quelle (SB j_man / MM j_12)?
- **RQ3 Kopplung:** Interaktionsterm in Einsparungen I_S = S_WT − S_W − S_T (S gegen (0,0) derselben HK-Stufe), I_S > 0 ⇔ Komplemente.
  Intervallformel: Teil E2.
Fallstudien: Stadtbach (SB) Hauptfall, Memmingen (MM) Gegenpol.

| Nr | Entscheidung |
|---|---|
| E1 | WP-Default-Kanal aus (Schalter B6). WP nur über die WRG-Quelle mit Lorenz-COP. Kein Fehler des alten Modells, sondern Rahmenwechsel. |
| E2 | WP fest an der Quelle (SB j_man). Standort variiert nur für den Speicher. |
| E3 | Keine Investitions-MILPs. Nur Festauslegung (B5). |
| E4 | HK0 (Messreihe 2025) und HK2, beide Netze. HK1 nur auf Rückfrage. |
| E5 | Zieljournal Energy (≈ 7.000 Wörter). |
| E6 | **Genauigkeit als Intervall:** jeder Lauf liefert [LB; UB] des Jahresbetriebswerts, Zielbreite ≤ 0,05 % (SB ≈ 12 k€, MM ≈ 200 €). **Weg A (bevorzugt):** Ganzjahreslauf mit fester Auslegung, `MIPGap=0.0005`, Zeitlimit 12 h; LB = Gurobi-Schranke, UB = Inkumbent. **Weg B (nur falls A scheitert):** Zeitzerlegung B9. |
| E7 | „Nicht aufgelöst“ (Intervall enthält 0) ist für jeden Effekt, besonders RQ3, ein zulässiges Ergebnis und wird so berichtet. Kein Nachrechnen, um eine Auflösung zu erzwingen. |

---

## Teil 0 — Laufende Läufe (sofort)

**Betroffen** ist ein Lauf mit bidirektionaler Zuleitung in einen Knoten, der seine Wärmebilanz über `Q_consumer` rechnet
(Knoten mit Anlagen oder Speicher). Das kommt nur auf `p2_v9_consolidation` nach v9-E5 vor; `hkw_to_ost` → j_ost (ohne Anlagen)
ist nicht betroffen. Die AC-Läufe auf `Loc_TES_Study_P2` sind laut deiner Prüfung nicht betroffen (`bidirectional=False`, belegt).
1. `output/_ac/PAUSE` — **erledigt 16:09**. Keine neuen Jobs aus `queue.json` starten.
2. `ac7_c20_k100` zu Ende laufen lassen (Zeitlimit ≈ 23 Uhr heute).
3. `ac7_c20_k000` **jetzt beenden**: seit 15:27 kein Logeintrag, ≈ 1 Kern Auslastung, Inkumbent = Referenz ohne Speicher, Ergebnis
   gehört nicht ins Paper. Wurzel-PID `25504` (`ac_run.sh`) mit ganzer Prozesskette beenden, Ausgabe nicht löschen, im Report belegen,
   dass kein Kindprozess übrig ist.
4. `ac10_k010_resume` und `ac10_s20_resume` in `queue.json` auf `aborted` setzen (kein Prozess vorhanden).
5. Die 8 wartenden AC-Jobs bleiben pausiert. Ihre Ergebnisse gehören zum alten Rahmen und gehen nicht ins Paper.
Prozesse anderer Konten nie anfassen. **Teil 0 führt nur die Session aus, die v12 ausführt**; die AC-Session bekommt den Hinweis, dass
`PAUSE` und `queue.json` ab jetzt hier liegen, und startet nichts mehr. `output/` ist nicht unter Git: Teil 0 wird im Report dokumentiert
(Zeitpunkt, Datei, Prozess-IDs), der Report sofort gepusht.

## Teil A — Diagnose (nur Lesen/Rechnen)

**A1 Systembilanz.** `R(t) = Σ Erzeugung − Σ Last − Σ Verluste − Σ Dump − Σ(Ladung − Entladung)`, **vorzeichenrichtig**
(Phantomwärme ⇒ R < 0). Für SB-PIN0 (v9), SB-C1, SB-C2 (v10), MM-PIN0. Achtung: Stundenschlüssel in `dump_audit.json` sind gegenüber
`dispatch_hourly.csv` um +1 h verschoben; vor jedem Abgleich ausrichten und das im Report belegen.
Zuerst den **Grundversatz** der sauberen Referenz erklären (SB-S0: R = +0,02…+0,26 MW, Σ 915 MWh/a): Modell oder Export?
Welche Verlust- oder Hilfsgröße fehlt? Danach C1/C2 quantifizieren, verdrängte KWK-/Kesselwärme in MWh und €.

**A2 Kontaminationsinventar.** Nur v9/v10-Läufe mit `hp_node` an j_man (J4) und Rückfluss prüfen. Belegen, dass v9-PIN0 0 Rückflussstunden
hat. MM-REF/MM-S1 explizit: betroffen ja/nein.

**A3 Default-Kanal.** Herkunft (Commit, Kommentar), Zweck, physikalische Quelle. Nur berichten.

**A4 Leistungspreis — abgeschlossen.** v11-M2 war ein Rechenfehler im Report: `REPORT_v11.md:230` nutzte 63.620 €/MW/a aus dem
Szenario „Netzentgelt −50 %“ (`scenarios.yaml:425`), der Basislauf rechnet mit 127.240 €/MW/a (`Stadtbach_topo.yaml:883`).
(2,960 − 0,329) MW × 127.240 €/MW = 334.768 € = berichtete Differenz. Kein Doppelansatz. Im Report nur diese Rechnung und eine
Korrekturnotiz zu v11-M2. Zusätzlich belegen: Jahresspitze oder Monatsspitzen (relevant nur für B9).

**A5 WP-Strom.** Ausdruck in der Strombus-Bilanz (Datei:Zeile), Vorzeichen von `Grid_sell_revenue_EUR`.

**A6 Kopplungen über die Zeit.** Liste alle Nebenbedingungen, die Stunden über Monatsgrenzen koppeln (Speicher-SOC, Mindestlauf-/
Stillstandszeiten, Rampen, Leistungspreis-Spitze, Jahresmengen, Leitungsverzögerung). Grundlage für B9.

## Teil B — Code (je Punkt eigener Commit und Test)

- [x] **B1 Systembilanz-Check.** R(t) vorzeichenrichtig in `validation.json` (min, max, Summe, Stunden < 0). Status `balance_fail`, wenn
  min R < −0,05 MW **oder** max |R| > 0,5 MW **oder** |Σ R| > 0,2 % der Jahreslast. Schwellen nach A1 nur verschärfen, nie lockern.
  Test: SB-PIN0/MM-PIN0 → `ok`, SB-C1 → `balance_fail`.
- [x] **B2 Fix `Q_consumer` bei bidirektionaler Zuleitung**, in **beiden** Zweigen: sekundärer Mischknoten (Z. 613–664) und
  Verbraucher mit Anlagen (ab ~Z. 700). Vorzeichenrichtiger Term wie an j_hkw (`_make_signed_q_fn`, Zufluss = +m_dot·cp·ΔT),
  Verluste genau einmal, Param-Assertion wie Z. 418–428. Test: 2-Knoten-Minimalnetz, 48 h, beide Flussrichtungen, R = 0.
- ~~B3 Demand Charge~~ — entfällt (A4: kein Modellfehler).
- [x] **B4 Residuum.** Alle Zielfunktionsterme einzeln gegen `pyo.value(model.obj)`. Ursache des 82.204 € suchen (max. ein Arbeitstag).
  **Keine Startbedingung:** ΔTAC wird immer aus dem Zielwert gerechnet. Ist die Ursache nicht gefunden, wird die Kostenzerlegung je
  Lauf mit ausgewiesenem Residuum geliefert und als vorläufig markiert.
- [x] **B5 Festauslegung** `CALION_FIXED_DESIGN=<yaml>`: WP MW, EK MW, TES-Stufe, cap_power, TES-Standort fixiert. Verbleibende
  Binärvariablen nach Block berichten.
- [x] **B6 Schalter** `CALION_HP_DEFAULT_CHANNEL=off|on`, Default off.
- [x] **B7 Laufprotokoll** `v12/runs_v12.csv` (Spalten Teil E).
- [x] **B8 Doku** Kopfkommentar `Stadtbach_topo.yaml` (W4).
- [ ] **B9 Zeitzerlegung (Weg B) — nur umsetzen, wenn C1-Weg-A die 0,05 % nicht erreicht.** Dann ohne Rückfrage:
  - Monatsblöcke (Blocklänge als Parameter). Je Block MIP-Gap 0,01 %.
  - **Spitze als äußerer Parameter:** Jahresleistungspreis r = 127.240 €/MW/a ist nicht blockweise zerlegbar. Raster P̄ ∈ {P_0 < … < P_n}
    (aus Weg-A-Lauf bzw. PIN0, wenige Werte). Mit Spitzen-Obergrenze P̄ zerfallen die Blöcke.
  - **UB (zulässig):** Blöcke nacheinander mit fixierter Spitzen-Obergrenze, Übergabe von SOC und Anlagenzuständen, **7 Tage
    Vorausschau** je Block (danach verworfen) oder Endbewertung des SOC mit Wasserwert λ. UB = min über P̄ von (r·P̄ + Σ Blockkosten).
  - **LB (Lagrange):** SOC-Kopplung dualisieren mit Wasserwerten λ_k (aus den Dualwerten bzw. Grenzkosten des UB-Durchlaufs):
    LB(P_i, P_{i+1}) = r·P_i + Σ_k Schranke_k[ min Kosten_k + λ_k·SOC_start,k − λ_{k+1}·SOC_end,k | Spitze ≤ P_{i+1} ];
    LB = min über i. Gültig für jedes λ. Übrige Kopplungen aus A6 relaxieren.
  - Test: auf das C0-Design anwenden, Ganzjahreswert muss in [LB; UB] liegen; Breite berichten.

## Teil C — Validierung (`CALION_RUN_TAG=v12`)

- [x] **C0 Regression:** SB-PIN0-HK0, MM-PIN0-HK0 ganzjährig mit neuem Code (inkl. B6 off). `status = ok`. Diese Dumps sind ab jetzt
  die Warmstart-Quelle (nicht die alten v9-Dumps).
- [x] **C1 SB-Test Weg A:** WP 8 MW an j_man, TES 146 MWh an j_man (prüft B2 mit Rückfluss), HK0, ganzjährig, `MIPGap=0.0005`,
  12 h. Breite-über-Zeit-Verlauf (Schranke, Inkumbent) berichten.
- [x] **C2 MM-Test Weg A:** WP 1 MW, TES = Median von `discrete_energies_mwh` der MM-Config ohne 0 (MWh und m³ berichten), HK0,
  `MIPGap=0.0005`, 4 h.
- [x] **C3 nur bei Weg B:** B9 auf C0- und C1-Design, Vergleich mit Weg A.

## Teil D — Kampagne

**D0 Startbedingungen (alle):** B1, B2, B5, B6 Tests grün; C0 `ok`; C1, C2 `ok`, min R ≥ −0,05 MW; Intervallbreite ≤ 0,05 % in C1 und C2
**entweder** über Weg A **oder** über Weg B (dann B9-Test und C3 grün); geschätzte Laufzeit Stufe 1 ≤ 4 Tage bei 2 Slots.
Sonst STOPP, Report mit Vorschlag. Die Kampagne nutzt durchgehend den Weg, der D0 erfüllt hat.

HK2: vor Stufe 1 für **beide** Netze die Herleitung der HK2-Reihe berichten (Formel, Min/Mittel/Max Vor- und Rücklauf) und belegen,
dass Netzphysik, COP, Maske und Speicher-ΔT dieselbe Reihe nutzen.

| Stufe | Netz | WP [MW] | TES [MWh] | TES-Standort | HK | Läufe |
|---|---|---|---|---|---|---|
| 1 | SB | 0, 8 | 0, 146 | j_hkw, j_man | HK0, HK2 | 12 |
| 1 | MM | 0, 1 | 0, Median-Stufe | j_9, j_12 | HK0, HK2 | 12 |
| 2 | SB | 0, 4, 8, 12 | 0, 73, 146, 292 | besserer Standort aus Stufe 1 je HK | HK0, HK2 | +24 |
| 3 | — | — | — | anderer Standort, HK1, MM-Raster | — | nur auf Rückfrage |

TES = 0 ist standortunabhängig (einmal rechnen). Reihenfolge: SB vor MM. Warmstart je Block aus C0 derselben HK-Stufe,
`CALION_SEED_FILL_ZERO=1`, nie zwischen Designs. Läufe mit `status != ok` nicht wiederholen, melden.
Nach Stufe 1 Zwischenreport; Stufe 2 startet ohne Rückfrage, wenn die Restzeit ≤ 5 Tage bei 2 Slots ist.

## Teil E — Lieferung für das Schreiben

runs_v12.csv je Lauf: scenario_id, Netz, HK, WP_MW, TES_MWh, TES_m3, TES-Standort, Status, UB, LB, Breite, Laufzeit, min R, max |R|, Σ R,
Kostenzeilen mit Residuum, WP Q_th/Q_el/SCOP, Volllaststunden, TES-Zyklen, Anteil Direktentladung vs. Vorwärmung, ΔT_TES,
KWK-Strom/-Wärme, Kesselwärme, Dump, Spitze Netzbezug.

`scripts/paper_2/v12_eval.py` → `v12/tables/`:
1. Einsparung S_A = TAC_0 − TAC_A je Rasterpunkt gegen (0,0) derselben HK als Intervall [LB_0 − UB_A; UB_0 − LB_A]
   (positiv = günstiger). TAC = Betriebswert + annuisierte Investition (fix je Design, auf LB und UB gleich addieren).
2. Interaktionsterm (RQ3), **nur in Einsparungen**: I_S = S_WT − S_W − S_T = TAC_W + TAC_T − TAC_0 − TAC_WT; I_S > 0 ⇔ Komplemente.
   Intervall aus den TAC-Schranken: **I_S ∈ [LB_W + LB_T − UB_0 − UB_WT ; UB_W + UB_T − LB_0 − LB_WT]**.
   Im Skript als Funktion mit Unit-Test (Zahlenbeispiel mit bekannten Werten) implementieren, damit das Vorzeichen nicht kippt.
3. Speicherwert je Standort und HK in €/a und €/MWh, Kapazität in MWh und m³ (RQ2).
4. Entlademodus und ΔT_TES je HK (RQ1).
5. Mechanismus: Kostenzeilen mit dem größten Beitrag (Top 5).
6. Break-even-Speicherkosten (€/m³) je Standort und HK aus Stufe 2.
7. Aussage je Effekt: „aufgelöst“ nur, wenn das Intervall die 0 nicht enthält.
Nur Datentabellen und je Kernfigur ein Entwurfsplot (PNG).

## Ablieferung
REPORT_v12.md: 0 → Widersprüche → Meldepflichten → A → B (mit Tests) → C → D → E. Zwischenreports nach C und nach Stufe 1.
STOPP nach Stufe 2 oder bei verletzter Bedingung.

## Änderungen gegenüber v12 (deine Kritik)
1. Gap 0,5 % → zertifiziertes Intervall aus Zeitzerlegung, Zielbreite 0,05 % (B9, E6). Statt eines engeren Ganzjahres-Gaps, das in
   8–12 h nicht erreichbar ist.
2. B1 vorzeichenrichtig, Grundversatz zuerst erklären, Schwellen gegen Phantomwärme asymmetrisch; Stundenversatz-Falle benannt.
3. Teil 0 neu: technisches Kriterium, PAUSE statt Beenden, alter Rahmen ≠ Fehler.
4. A2 eingegrenzt, B2 deckt den Zweig „Verbraucher mit Anlagen“ ab.
5. Warmstart aus v12-C0, MM-Stufe als Regel, HK2 für beide Netze, B4 keine Startbedingung.

## Änderungen v12.1 → v12.2 (deine zweite Kritik)
- Weg A (Ganzjahr, MIPGap 0,05 %, 12 h) zuerst; B9 nur als Ausweichweg, dann mit Lagrange-Wasserwerten für LB, Vorausschau für UB,
  Jahresspitze als äußerem Parameter. Begründung: feste Auslegung ist 5–10× schneller als Investition (SB-PIN0 3,8–7,9 h bis 0,15 %).
- „Nicht aufgelöst“ zulässig (E7).
- **Deine I_S-Formel hatte das Vorzeichen vertauscht:** [LB_0 + LB_WT − UB_W − UB_T; UB_0 + UB_WT − LB_W − LB_T] ist das Intervall von
  −I_S. Korrekt ist die Formel in Teil E2, mit Unit-Test.
- A4: der 2×-Faktor aus v11 kann vom falschen Satz (63.620 statt 127.240 €/MW/a) im Report stammen.
- Teil 0: nur eine Session, Doku statt Commit für `output/` (in `.gitignore`).

## Änderungen v12.2 → v12.3 (dein Bericht 16:10)
- `PAUSE` erledigt; `k000` sofort beenden statt bei Teil C.
- A4 abgeschlossen (v11-M2 war Rechenfehler im Report), B3 entfällt.
- **Diese Session führt v12 aus**, einschließlich Teil 0.
