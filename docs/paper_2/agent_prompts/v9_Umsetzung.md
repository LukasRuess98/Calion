# AGENT-AUFTRAG Paper 2 — v9 „Umsetzung Modellkonsolidierung“ (2026-10-23)

Zuerst: Lege diesen Auftrag unverändert als `docs/paper_2/agent_prompts/v9_Umsetzung.md` ab.

Antwort auf `docs/paper_2/agent_reports/v8/REPORT_v8.md` (main@41facaa). Code-Änderungen sind jetzt erlaubt, nur für die unten
mit [x] markierten Punkte, auf einem neuen Branch `p2_v9_consolidation` (abgezweigt von `Loc_TES_Study_P2`). Jede Änderung mit
Env-Schalter für das Altmodell. Keine Änderung an bestehenden Ergebnisdateien. Läufe nur, wo unten ausdrücklich freigegeben.
Ablage Report `docs/paper_2/agent_reports/v9/`. Nach Teil C STOPP.

Korrekturen zu v8:
- B3 „E6-Sweep bleibt orthogonal zu E1–E3 nützlich“: nein. Wenn die Entladung des atmosphärischen Tanks bei realer Temperatur
  größtenteils gesperrt oder eingeschränkt ist, verschieben sich alle Break-even-Punkte des Leistungskosten-Sweeps. Die wartenden
  Läufe sind Altmodell-Sensitivitäten, nicht E6-Ergebnisse.
- E3b als „groß“ eingestuft: Bei fester Temperaturreihe ist Vorwärmung linear (siehe B3 unten), Aufwand eher mittel.
- A2a MM „nicht kalibrierbar“: Import_Data_Memmingen_epronet_cleaned.xlsx enthält Vor- und Rücklauftemperaturen je
  Übergabestation (V_n_flow_temp, V_n_return_temp). Die sind für die Kalibrierung nutzbar (siehe A2).

## Teil A — Vorprüfungen (nur Lesen/Rechnen)

A1 Jahresgleichheit. Aus welchem Jahr stammen in SB Last-, Preis-, Außentemperatur- und WRG-Reihen, und aus welchem die
Messreihen HKW_Temp_VL/RL.xlsx (2025)? Stündlicher Zeitstempelabgleich, Zeitumstellung, Lücken (Anzahl, längste).
Wenn gleiches Jahr: Messreihe direkt als HK0 verwendbar. Sonst: kalibrierte Kurve (v8 A2b) für VL, Regressionsmodell für RL.
A2 MM-Kalibrierung. Aus den Stationsreihen: lastgewichtete mittlere Vorlauf- und Rücklauftemperatur je Stunde; Kalibrierung
von compute_heizkurve wie v8 A2b; Stunden > 95 °C; Vergleich mit heutigem T_VL_ts und Netzpfad (v8 A3).
A3 Mindesttemperaturen der Verbraucher. Welche Mindest-Vorlauftemperaturen sind für SB-Verbraucher dokumentiert
(Industrie: MAN, KUKA, Klinikum; Kommentar consumer_min_temp_c)? Gibt es Belege, warum die Anlage 2025 nie unter 87 °C fuhr?
Das begrenzt, wie weit HK1/HK2 in SB realistisch absenken können.
A4 Rücklauf als Speichergrenze. Aus HKW_Temp_RL: Mittel, P10, P50, P90, mittlerer Rücklauf in Stunden mit S1-Entladung.
Daraus ΔT_TES = 95 °C − T_RL für Mittel und P90.

## Teil B — Umsetzung (nur [x]-Punkte)

- [x] B1 = E1 Einheitliche Temperatur. Der Runner erzeugt je Netz und HK-Stufe eine stündliche Vorlauf- und Rücklaufreihe
  und injiziert sie als supply_temp_dict/return_temp_dict; dieselben Reihen speisen COP, Maske/Vorwärmung und Speicher-ΔT.
  SB-HK0 = Messreihe (oder kalibrierte Kurve, je nach A1), MM-HK0 = Kalibrierung aus A2 (falls R² ≥ 0,6, sonst heutige Kurve, Vermerk).
  Assertion nach Build: model.supply_temp_series[t] == T_VL[t] für alle t. Env CALION_LEGACY_TEMPERATURE_FRAME=1 = Altmodell.
- [ ] B1b HK1/HK2 neu definieren (erst nach Rückmeldung von Lukas zu A3). Vorschlag: HK1 = HK0 − 10 K Vorlauf, − 5 K Rücklauf;
  HK2 = HK0 − 20 K Vorlauf, − 10 K Rücklauf; jeweils mit Untergrenze aus A3. Im Report nur die Reihen und Kennzahlen zeigen
  (Mittel, Stunden > 95 °C), nicht in die Configs schreiben.
- [x] B2 = E2 Speicher-ΔT. delta_T_scenario_k = t_store_max_c − T_RL,ref mit T_RL,ref = Jahresmittel der Rücklaufreihe der
  jeweiligen HK-Stufe (Sensitivität: P90 per Env). Hydraulische Anbindungskappe mit demselben ΔT. Env CALION_TES_DELTA_T_MODE=legacy_floor.
- [x] B3 = E3b Vorwärmbetrieb als Basis, E3a als Sensitivität. Für einen atmosphärischen Tank (T_store = 95 °C):
  α(t) = max(0, (T_VL(t) − T_store)/(T_store − T_RL(t))). Nebenbedingung je Stunde: Nachheizwärme am TES-Knoten von brennstoff-
  oder strombetriebenen Erzeugern ≥ α(t)·Q_dis(t) (lineare Bedingung, α(t) als Parameter). Die Entladeleistung zählt voll als
  Speicherwärme, die Nachheizung als Erzeugung des jeweiligen Erzeugers. Prüfen und dokumentieren, welche Erzeuger am Knoten
  nachheizen dürfen (j_hkw: HKW, Kessel, EK, KWK). Env CALION_TES_DISCHARGE_MODE=mask = binäre Maske gegen dieselbe Reihe (E3a).
  Testfall: bei T_VL ≤ 95 °C ist α = 0 und das Ergebnis identisch mit Maske-aus.
- [ ] B4 = E4 Druckbehälter. Nur Recherche: Primärquelle für Kosten eines druckbeaufschlagten Wärmespeichers (≥ 110 °C) mit
  Volumenbezug, Geltungsbereich, Umrechnung auf das degressive Kostenmodell. Nicht implementieren.
- [x] B5 = E5 Topologie. hkw_to_man bidirektional; ek_sb bleibt an j_hkw (nur hp_sb nach j_man). Prüfen, ob eine
  Einspeisepumpe/Druckhaltung an j_man im Modell abgebildet ist; wenn nicht, als Limitation im Report vermerken (keine Kosten erfinden).
- [x] B6 = E6 neues Kostenmodell (§4cr/§4cs) als Standard der neuen Version.

Commit-Disziplin: ein Commit je Punkt, Tag p2-v9-model nach Teil C, Rezeptur aller Env-Schalter in docs/paper_2/agent_reports/v9/MODEL_V9.md.

## Teil C — Verifikation

- C1 Build-only-Tests je Netz × HK0 für jeden Punkt (erwartete Kennzahlen: Logzeile Temperaturpfad, Assertion grün, ΔT_TES,
  E_max je Rung, α-Statistik (Stunden α > 0, Mittel, Max), Leitungsrichtung hkw_to_man mit Vorzeichen, EK-Knoten).
- [x] C2 Lauf SB-PIN0-HK0 und MM-PIN0-HK0 im Modell v9 (je ein Lauf, Matched-Effort-Standard). Vergleich mit Altmodell-PIN0:
  Δ TAC je Kostenposition, Netzverluste, Bilanzschluss. Erst danach STOPP, keine Investitionsläufe.
- [ ] C3 Warteschlange: wartende AC/AE/AF-Jobs aus queue.json zurückstellen (laufende fertig laufen lassen). Nur wenn Lukas ankreuzt.

## Ablieferung
v9/REPORT_v9.md: A1 → A4 → A3 → A2 → B1 → B2 → B3 → B5 → B6 → C1 → C2 → B4. Vorab „Widersprüche“ und „Meldepflichten“. STOPP.
