# AGENT-AUFTRAG Paper 2 — v10 „Prüfpunkte + Kernlaufsatz Modell v9" (2026-10-29)

Zuerst: Lege diesen Auftrag unverändert als `docs/paper_2/agent_prompts/v10_Kernlaufsatz.md` ab.

Antwort auf `docs/paper_2/agent_reports/v9/REPORT_v9.md` (main@c784c10, Tag `p2-v9-model`). Basis aller Läufe: Tag `p2-v9-model`
ohne Legacy-Env. Code-Änderungen nur für Teil B, auf `p2_v9_consolidation`, je mit Env-Schalter und eigenem Commit.
Läufe nur für die mit [x] markierten Punkte in Teil C, sequenziell (v9-M3), Ressourcengrenze wie bisher.
Report unter `docs/paper_2/agent_reports/v10/`, auf `main` spiegeln. Nach Teil C STOPP.

Übernommen aus v9: A1 (Messreihe 2025 = SB-HK0), A4 (ΔT_TES 33,47 K), B1–B3, B5, B6, C1, C2, B4 (Negativbefund).
Die Vorwärm-Nebenbedingung (Serienschaltung Tank → Nachheizer) ist physikalisch korrekt formuliert.

---

## Teil A — Prüfpunkte (nur Lesen/Rechnen, vor jedem Lauf)

A1 MM `Pressure_slack_cost_EUR` (11.380 €/a in v9-PIN0). Das ist 2,7 % der MM-TAC und größer als jeder bisher gemessene
MM-Speicherwert (1–2 k€/a); die STOPP-Regel (Hilfsterme > 20 % des Δ) würde bei jedem MM-Vergleich greifen.
(a) Je Knoten/Leitung und Monat: Stunden mit Slack > 0, Summe, Kosten.
(b) Hypothese prüfen: Unter v9 fährt MM im Mittel 82,6 °C statt ≈ 91,9 °C (v8 A3) bei konstantem Rücklauf 63,6 °C; die Spreizung
sinkt von ≈ 28 K auf ≈ 19 K, der Massenstrom steigt um ≈ 45 %, Druckverluste steigen und die Druckhaltung bindet.
Massenstrom- und Druckverlustvergleich alt vs. v9 für die Leitungen mit Slack.
(c) Ist der Slack ein Hinweis, dass die MM-Heizkurve hydraulisch mit dem Bestandsnetz nicht fahrbar ist? Einschätzung mit Zahlen.

A2 Ladeseite des Tanks. E2 setzt die Energiedichte auf 95 °C − T_RL. In Stunden mit T_VL(t) < 95 °C (SB: 43 % der Stunden,
Messung min. 87,4 °C) kann Wasser aus dem Netz den Tank nicht auf 95 °C laden. Prüfe am Code, woher die Ladewärme des Tanks
an j_hkw stammt (nur Knotenerzeuger oder auch Netzzufluss über Leitungen?). Schätze offline aus dem v7-S1-Dispatch, wie viel
Ladung in Stunden mit T_VL < 95 °C anfiele und welcher Anteil davon von Knotenerzeugern (hkw, p2h_existing, ek_sb) gedeckt wäre.

A3 Maske im Vorwärmmodus. Belege am Build-Log oder der Constraint-Zählung, dass im Modus preheat keine qd_mask-Constraint
gebaut wird (nur *_preheat_topping). Ersetze außerdem die Abfrage "T_RL_ts" in dir() (scenario_runner ~Z. 759) durch eine
explizite Variable; reine Robustheitsänderung ohne Verhaltensänderung (eigener Commit, Testfall: α-Statistik unverändert).

## Teil B — Modelländerungen (nur [x])

- [ ] B1 Ladeseitige Bedingung (nur falls A2 zeigt, dass Netzzufluss den Tank lädt). In Stunden mit T_VL(t) < T_store gilt
  Q_charge(t) ≤ Σ Q_th_out der Knotenerzeuger (nur sie können 95 °C liefern). Spiegelbild der Vorwärm-Bedingung, linear.
  Env CALION_TES_CHARGE_MODE=free = heutiges Verhalten. Testfall: bei T_VL ≥ 95 °C unwirksam.
- [x] B2 Szenario S3 im Modell v9 (Tank an j_man). Unter E2 ist die normale Ladung an j_man (S2: WP lädt mit Netz-COP auf 95 °C)
  physikalisch inkonsistent. Der Tank an j_man wird nur als S3 (Heißladung durch die WP mit COP bei 95 °C) gerechnet; S2 entfällt.
  Prüfen, dass die Heißlade-Kopplung mit E1 (gemessene Reihe) und E2 (ΔT 33,47 K statt 35 K) konsistent ist; Abweichung melden.

## Teil C — Kernlaufsatz (nur [x], sequenziell)

Für alle Läufe: Warmstart vom PIN0-Dump des jeweiligen Netzes (v9-C2) mit CALION_SEED_FILL_ZERO=1, niemals Transplantation
zwischen TES-Standorten. Matched-Effort-Standard (MIPFocus 3, Ziel-Gap 0,15 %, SB TimeLimit 48 h, MM 4 h). Solution count und
Inkumbentenverlauf aus dem Gurobi-Log. Wert-Intervalle nach Y1 gegen PIN0 (Paketwert) und gegen die speicherfreie Referenz
(reiner Speicherwert). STOPP-Regel Hilfsterme > 20 % des Δ prüfen und melden.

| Nr. | Lauf | Zweck | Reihenfolge |
|---|---|---|---|
| [x] C1 | SB-REF-HK0: WP/EK frei, TES strikt aus (discrete_energies_mwh: [0]) | Referenz für reinen Speicherwert; zeigt Wirkung E5 (WP-Einspeisung, EK an j_hkw) | 1 |
| [x] C2 | SB-S1-HK0: TES an j_hkw, Vorwärmmodus, c0×1,0 | Kernergebnis | 2 |
| [x] C3 | MM-REF-HK0 und MM-S1-HK0 (TES an j_9) | Gegenpol; nur wenn A1 den Slack erklärt hat | 3 |
| [ ] C4 | SB-S1-HK0 mit CALION_TES_DISCHARGE_MODE=mask | Wert des Vorwärmbetriebs (E3a vs. E3b) | 4 |
| [ ] C5 | SB-S1-HK0 mit c0×2,0 (≈ KWW-Katalogpreis 500 €/m³) | Preisstand Deutschland | 5 |
| [ ] C6 | SB-S3-HK0 (TES an j_man, Heißladung WP) | Topologie/Standort | 6 |
| [ ] C7 | MM-S3-HK0 (TES an j_12, Heißladung WP) | Kopplung WP-COP ↔ Speicher am selben Knoten | 7 |

Je Lauf berichten: TAC, Gap, Solution count, Status; gebaute WP/EK/TES (MW, MWh, m³, Behälter, Leistung, Knoten);
Kostenzerlegung gegen PIN0 und gegen REF (Positivliste aus v5 B1); WP-Einspeisung über hkw_to_man (MWh/a, Stunden mit
Rückfluss); Speicherbetrieb (Vollzyklen, Entladung in Stunden mit α > 0 und mittleres α dort, Nachheizwärme MWh/a und nach Erzeuger);
Bilanzschluss; Laufzeit und RAM.

Vorab eine Zeitschätzung je Lauf aus C2 (SB-PIN0 7,7 h) und Startplan mit erwarteten Endzeiten.

## Ablieferung
v10/REPORT_v10.md: A1 → A3 → A2 → B2 → (B1) → Zeitplan → C1 → C2 → C3 → weitere. Nach jedem fertigen Lauf ein kurzer Zwischen-Commit
mit den Kennzahlen. Nach Teil C STOPP.
