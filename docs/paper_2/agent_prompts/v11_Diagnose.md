# AGENT-AUFTRAG Paper 2 — v11 „Diagnose v10 + Wechsel auf Festauslegungs-Enumeration" (2026-11-02)

Zuerst: Lege diesen Auftrag unverändert als `docs/paper_2/agent_prompts/v11_Diagnose.md` ab.

Antwort auf `docs/paper_2/agent_reports/v10/REPORT_v10.md` (p2_v9_consolidation@e2ea894). Teil A: nur Lesen und Rechnen auf den
vorhandenen v10-Läufen (Lösungsdumps, Zeitreihen). Teil B: kleine Code-Änderungen nur mit [x]. Teil C: Läufe nur mit [x].
Report `docs/paper_2/agent_reports/v11/`, auf `main` spiegeln. Nach Teil C STOPP.

Übernommen aus v10: A1 (MM-Slack: 6 h im Dezember, Spreizung 18,9 K, plausibel erklärt), A3, B2, MM-Ergebnis (kein Zubau, gut konvergiert).

Nicht übernommen, weil widersprüchlich oder unvollständig:
- C1 (SB-REF): WP-Wärme vs. MAN-Last. Die WP an j_man liefert 48.886 MWh/a, MAN braucht 17.720 MWh/a (v8 A1), und hkw_to_man
  hat laut Report 0 Stunden Rückfluss. Dann kann die WP höchstens die MAN-Last decken. Gleichzeitig steigt der Dump von 538 MWh
  (PIN0) auf 79.039 MWh (C1) bzw. 86.067 MWh (C2).
- STOPP-Regel nicht angewendet. C1: Dump_cost 395.193 € gegenüber PIN0 ≈ 2,7 k€ → Δ Hilfsterm ≈ 392 k€ = ≈ 29 % des Δ
  von 1,36 Mio. € (> 20 %). C1 ist damit nach unserer eigenen Regel nicht verwertbar, bis der Dump erklärt ist.
- v10-M2 (Residuum 82.204 €): Vermutung zur Prüfung: die bepreiste Anbindungsleistung des Tanks fehlt in der Kostenzerlegung.
  28.200 €/MW × 38,8 MW = 1,094 Mio. €; × (ANF 0,0651 + O&M 0,005) ≈ 76,6 k€/a (sehr nahe am Residuum).
- EK-Leistung in C1/C2 fehlt erneut (ek_sb an j_hkw ist investierbar).

## Teil A — Diagnose (nur Lesen/Rechnen)

A1 Wärmebilanz j_man (C1, C2), stündlich. WP-Wärme (hp_sb, getrennt nach WRG-Kanal und Default-COP-Kanal falls vorhanden),
MAN-Last, Leitungsfluss hkw_to_man mit Vorzeichen (flow_dir und m_dot bzw. m_dot_abs, Wärmestrom in MW), Dump an j_man.
Jahressummen, Stunden mit Rückfluss, Stunden mit Dump > 0. Schließt die Bilanz WP + Zufluss = MAN + Dump + Verluste?
Erkläre die 48.886 MWh. Falls der Report die Leitung falsch ausgewertet hat (Richtung, Spalte): korrigieren.

A2 Dump nach Knoten und Ursache (PIN0, C1, C2). Je Knoten: MWh/a, Stunden, Kosten; Dump-Preis [€/MWh] aus Config.
Welcher Erzeuger produziert in den Dump-Stunden am jeweiligen Knoten (WP, KWK, Biomasse, AVA)? Physikalische Deutung
(Notkühler am Kraftwerk für stromgeführte KWK? Abwärme-Rückkühlung an j_man?). Ist ein Dump an j_man im realen Netz vorhanden?
STOPP-Regel je Vergleich (C1−PIN0, C2−PIN0, C2−C1) ausrechnen und ausweisen.

A3 Strom der WP. Elektrische Arbeit der WP [MWh/a], COP-Jahresmittel, woher kommt der Strom (Netzbezug vs. Eigenerzeugung
KWK, Bilanz am Strombus), warum bleibt Grid_energy_cost in C1 praktisch unverändert (+426 €)? Ist die Quellenbegrenzung
WRG1Q_MW (max. 11,73 MW) in jeder Stunde eingehalten (Q_wrg ≤ WRG1Q_MW), und gibt es einen Default-Kanal ohne Quellbegrenzung?

A4 v10-M2. Prüfe die Vermutung oben (Code-Pfad von power_capex_eur_per_mw * cap_p in _capex_raw_expr gegen die
Kostenzerlegung in result_collector.py). Wenn bestätigt: Kostenzeile ergänzen (Teil B1), sonst weitersuchen.

A5 Gebaute Leistungen C1/C2: ek_sb [MW] aus dem Lösungsdump, EK-Strom [MWh/a], Lastspitze Strombezug [MW] und in welchen Stunden
sie entsteht (Treiber des Leistungsentgelts +334.769 € in C2).

A6 Konvergenz. Für C1 und C2: Verlauf von Schranke und Inkumbent (Zeit, Wert), Anteil der Binärvariablen nach Block
(WP-Größe, TES-Stufen, Betriebszustände, Leitungsrichtung flow_dir). Hat die neue bidirektionale Leitung (8.760 Richtungs-
binärvariablen) oder die Vorwärm-Bedingung die Schranke verschlechtert? Vergleich mit PIN0.

## Teil B — Code (nur [x])

- [ ] B1 Kostenzerlegung: fehlende Kostenzeile ergänzen (nur wenn A4 die Ursache belegt), Assertion Residuum < 1 € als Fehler
  statt Warnung.
- [x] B2 Ergebnisarchiv: Kein Lauf darf ein bestehendes Ausgabeverzeichnis überschreiben (v10-M1). Ausgabe unter
  output/<tag>/<scenario_id>/ mit Tag je Kampagne; force_rerun auf ein belegtes Verzeichnis bricht ab. Bestehende v9/v10-Läufe
  einmalig in diese Struktur verschieben (nicht löschen).
- [ ] B3 Festauslegungs-Modus (CALION_FIXED_DESIGN=<pfad>): alle Bau-, Größen- und Leistungsvariablen aus einer Designdatei
  fixieren (WP MW, EK MW, TES-Stufe, cap_power), nur Betrieb lösen. Designdatei als kleines YAML. Testfall: Design aus C1
  fixieren und den C1-Zielwert innerhalb seines Gaps reproduzieren.

## Teil C — Läufe (nur [x], nach Teil A)

- [ ] C1 Laufzeittest Festauslegung: C1-Design fixiert (B3), SB-HK0. Laufzeit, Gap, Zielwert gegen C1. Abbruch nach 8 h.
- [ ] C2 Enumerationsplan (nur Plan, kein Lauf): Raster WP {0, 4, 8, 12, 16 MW} × TES {0, 73, 146, 292, 438 MWh}, je Netz,
  nur wenn C1 ≤ 4 h je Lauf ergibt. Gesamtzeit, Slot-Bedarf, Reihenfolge.

## Ablieferung
v11/REPORT_v11.md: A1 → A2 → A3 → A4 → A5 → A6 → B → C. Vorab „Widersprüche" und „Meldepflichten". Nach Teil C STOPP.
