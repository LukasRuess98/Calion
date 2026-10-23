# AGENT-AUFTRAG Paper 2 — v8 „Modellkonsolidierung vor jedem weiteren Lauf“ (2026-10-23)

Zuerst: Lege diesen Auftrag unverändert als `docs/paper_2/agent_prompts/v8_Konsolidierung.md` ab und committe ihn mit dem Report.

Antwort auf `docs/paper_2/agent_reports/v7/REPORT_v7.md` (main@42444bb). Teil A ist nur Lesen und Offline-Rechnen (Regeln v5 §0).
Teil B ist ein Umsetzungsplan mit Freigabe-Gates: nichts implementieren, bevor Lukas die Entscheidungen in B0 angekreuzt hat.
Ablage `docs/paper_2/agent_reports/v8/`, ≤ 150 KB, nach Teil A STOPP.

Übernommen aus v7: T1 (SB-Netzphysik = temperature_frame), T3 (Messreihe HKW-Vorlauf 2025: 87,4–124,4 °C, Mittel 99,9 °C,
4.974 h > 95 °C), H1 (m_dot_max ist harte Schranke), M1/M2 (Speicherwert über strompreisgeführte KWK, +376.038 €/a exakt), D1.

Korrekturen zu v7:
- H1/H2 rechnen mit 15 K, die Netzphysik aber mit temperature_frame (Vorlauf 84–115 °C, Rücklauf 60–62 °C, also 22–53 K).
  Die 20,9 MW, 17,7 MW Restkapazität und 3,2 MW MAN-Spitze sind damit falsch skaliert. Neu rechnen mit dem stündlichen ΔT des Netzpfads.
- D1-Einordnung: 5.439.000 € / 438 MWh = 12.418 €/MWh, nicht ≈ 13.600.
- W2: Biomasse läuft in PIN0 bereits 8.760 h; der Spread 70,79 €/MWh (Biomasse als Ladequelle) ist daher keine plausible
  Obergrenze. Ladequelle nach M2 ist überwiegend Gas-KWK in teuren Stunden.

---

## Teil A — Prüfungen (nur Lesen/Rechnen)

A1 Stichknoten j_man (neu, hohe Priorität). hkw_to_man (Stadtbach_topo.yaml Z. 345–351) hat kein `bidirectional: true`;
laut pipe_pair.py ~Z. 170/291 ist die Leitung dann einseitig (j_hkw → j_man, m_dot ≥ 0). j_man hat nur den Verbraucher MAN_MW.
Vermutung: WP, EK und Speicher an j_man können nur die MAN-Last decken, nicht ins Netz speisen.
(a) Bestätigen am Code (Domain von m_dot für nicht-bidirektionale Leitungen, Knotenbilanz j_man, gibt es dort Notkühler/Dump?).
(b) Stündlich für v7_final/SB-S1-HK0, SB-S2-HK0, SB-S3-HK0: WP-Wärme hp_sb vs. MAN-Last; Stunden, in denen die WP-Wärme
durch die MAN-Last begrenzt ist (WP = MAN-Last oder WP unter Mindestlast abgeschaltet), Jahres-MWh beider Größen, MAN-Last-Statistik
(Mittel, P5, P50, P95, Max, Sommermittel).
(c) Folge für die Ergebnisse: Ist die gebaute WP-Größe (1,8–2,5 MW) und EK = 0 durch die MAN-Last erklärbar? Ist S2/S3 build=0
strukturell erzwungen (Tank an j_man kann nur MAN versorgen)? belegt/berechnet/vermutet.
(d) Gleiche Prüfung für MM j_12 (Leitungsrichtungen, lokale Last, Einspeisung ins Netz möglich?).

A2 Messdaten. (a) Gibt es neben HKW_Temp_VL.xlsx eine Rücklauf-Messreihe (HKW, PPS, PSW) und Messreihen für MM?
Statistik wie T3. (b) Kalibriere compute_heizkurve (k, T_VL_min, T_VL_max; T_heiz und T_aus,design fest) per Kleinste-Quadrate auf
die SB-Vorlauf-Messreihe gegen die Außentemperatur des Datensatzes: Parameter, R², RMSE, Stunden > 95 °C der kalibrierten Kurve.
Gleiches für MM, falls Daten vorhanden. (c) Wie gut trifft temperature_frame die Messung (RMSE, Stunden > 95 °C je Saison)?

A3 Temperaturpfad MM. Der Runner setzt network.heating_curve.T_supply_min_c/max_c (scenario_runner.py ~Z. 418–423),
k und die Stützstellen (−15/30 °C vs. −12/15 °C) aber nicht. Stündliche Differenz Netzpfad MM vs. T_VL_ts für HK0/HK1/HK2
(Mittel, Max, Stunden > 95 °C je Pfad).

A4 Wertschranke W2 neu. Grenzkosten der Ladewärme stündlich (KWK mit stündlicher Stromgutschrift), Ladung aus M2-Zuordnung.
Verdrängbare Gaskesselwärme in gesperrten Stunden (leistungs- und blockgedeckelt) × stündlicher Spread. Drei Varianten:
Maske nach Heizkurve (2.033 h), nach Messung (4.974 h), nach temperature_frame (6.552 h). Jeweils auch: Wie viel von der heutigen
S1-Entladung (30.636 MWh) fällt in Stunden, die bei messbasierter Maske gesperrt wären, und welcher Anteil des Speicherwerts hängt
daran (Spread × MWh)?

A5 Netztemperaturabhängigkeit von PIN0 (offline). Wärmeverluste des Netzes je Temperaturpfad (Heizkurve, Messung,
temperature_frame) mit den Leitungsdaten und U-Werten der Topologie: Jahres-MWh und Kosten. Grobe Schätzung, wie stark sich PIN0
ändert, wenn die Netzphysik auf die gemessene Temperatur umgestellt wird.

---

## Teil B — Umsetzungsplan (nur Plan und Aufwand; Umsetzung erst nach Freigabe)

B0 Entscheidungen (Lukas kreuzt an, der Agent setzt nur Angekreuztes um):
- [ ] E1 Temperaturbasis: HK0 = auf Messung kalibrierte Heizkurve (A2b); Netzphysik, COP, Maske und Speicher-ΔT nutzen dieselbe
  stündliche Reihe (supply_temp_dict/return_temp_dict aus dem Runner). HK1/HK2 = relativ dazu definiert (neue Stufen vorschlagen).
- [ ] E2 Speicher-ΔT: ΔT_TES = T_store,max − T_RL (atmosphärisch 95 °C) statt 15-K-Boden; hydraulische Anbindungskappe mit demselben ΔT.
- [ ] E3 Entladung: (a) binäre Maske gegen dieselbe Netztemperatur wie E1, oder (b) Teilentladung als Vorwärmung.
- [ ] E4 Speichertechnologie: druckbeaufschlagter Tank (z. B. 120 °C, ohne Maske, eigene Kosten) als Alternative zum
  atmosphärischen; vorhandenen pressurized-Pfad prüfen und Kostenquelle nennen.
- [ ] E5 Topologie j_man: hkw_to_man bidirektional (Einspeisung MAN-Abwärme ins Netz) und EK an j_hkw statt j_man.
- [ ] E6 Kostenmodell: neues Modell (§4cr/§4cs: Leistung bepreist, 28,2 k€/MW, H/D 1,5, 45 m) als Basis.

B1 Für jede Entscheidung: betroffene Dateien/Zeilen, Änderungsumfang, Testfall (Build ohne Solve mit erwarteter Kennzahl,
z. B. Maskenstunden, ΔT_TES, E_max je Rung, Leitungsrichtung), Konsistenz-Assertion im Code (z. B. „Maske und Netzpfad nutzen
dieselbe Reihe“), Rückwärtskompatibilität (Altmodell per Env reproduzierbar?).

B2 Laufplan nach Umsetzung. Minimaler Kernsatz je Netz: PIN0, speicherfreie Referenz, freie Investition, je HK0/HK2 und je
Speichertechnologie (E4). Je Zeile: Laufzeit (aus vorhandenen Läufen geschätzt), RAM, Slot-Bedarf bei CPU-Kappe 50 %.
Wo reicht ein Lauf mit fixierter Auslegung statt eines vollen MILP? Gesamtdauer in Tagen.

B3 Warteschlange der AC/AE/AF-Session. Liste der laufenden und wartenden Läufe mit Startzeit und erwartetem Ende. Welche davon
bleiben nach E1–E6 verwertbar (z. B. als Altmodell-Sensitivität), welche nicht? Nichts anhalten, nur auflisten.

## Ablieferung
v8/REPORT_v8.md: A1 → A2 → A4 → A3 → A5 → B3 → B1 → B2. Vorab „Widersprüche“ und „Meldepflichten“. Nach Commit STOPP.
