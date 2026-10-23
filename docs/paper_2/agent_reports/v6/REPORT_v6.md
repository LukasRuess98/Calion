# REPORT v6 — Kopplung Speicher-Vorlauf-Standort (Agent-Auftrag v6.1, 2026-10-22/23)

Reihenfolge: A2 → B2 → B4 → A1 → B1 → B5 → B7 → B3 → B6 → B8 → A3 → A4 → C.
Regeln wie v5 §0 (belegt/berechnet/vermutet, keine Codeänderung, kein Solve). Ressourcen: CPU/RAM je ≤50% (Nutzervorgabe).

## Widersprüche zu den Angaben im Auftrag
- **B3-Prämisse:** Der Auftrag sagt "WP/EK-Standorte: SB j_hkw (`Stadtbach_topo.yaml` Z.151)". Z.151 (`j_hkw: assets:
  [hkw, p2h_existing, ek_sb, hp_sb, tes_sb]`) ist aber nur der STATISCHE Basis-Default — zur Laufzeit verschiebt
  `scripts/paper_2/scenario_runner.py:_apply_hp_location` (Zeilen 1101-1134) `hp_sb`/`ek_sb` in JEDEM
  SB-Investitionsszenario zum Knoten aus `scen_cfg["hp_nodes"][network][scen["hp_node"]]` — und das ist laut
  `scenarios.yaml` **j_man**, nicht j_hkw. Die **effektive** WP/EK-Position in allen vier geprüften SB-Läufen
  (S1, S2, S3, wie unten in B3 bestätigt) ist also **j_man**, wie in meinem Tranche-1-B4/B5 angenommen — der
  Auftragstext (vermutlich aus der statischen Topologie-Datei gelesen, ohne die Laufzeit-Verschiebung zu kennen)
  ist hier ungenau. Der separate Kopfkommentar-Defekt (j_ava) bleibt wie vom Auftrag selbst vermutet ein reiner
  Doku-Fehler — siehe B3 unten.
- **B5-Prämisse:** Der Auftrag sagt "In S3 liegt der Tank an j_man, die WP an j_hkw". Nach
  `configs/paper_2/scenarios.yaml` (`hp_nodes: stadtbach: J4: j_man # ... every SB investment scenario uses this`)
  ist es GENAU UMGEKEHRT: die WP (`hp_sb`/`ek_sb`) sitzt in JEDEM SB-Investitionsszenario fest an j_man — auch in
  S1 (wo der Tank an j_hkw sitzt, WP aber an j_man, also KNOTEN-ÜBERGREIFEND). In **S3** sitzt der Tank EBENFALLS
  an j_man (`tes_nodes: stadtbach: S3: "j_man"`) — WP und Tank sind in S3 also AM GLEICHEN Knoten, nicht an
  verschiedenen. Siehe B5 unten für die Konsequenz (sie ist tatsächlich eine gute Nachricht, keine neue
  Meldepflicht).

## A2 — Temperaturkonsistenz der Entlademaske (höchste Priorität)

### A2a — Was ist `T_supply_C` in `dispatch_hourly.csv`? Welcher Codepfad?
Antwort: `T_supply_C` ist die **Vorlauftemperatur der Rohrleitung, deren Name als erste Spalte in Dateireihenfolge
auf `_T_supply_in` endet** (`scripts/paper/extract_artefacts.py:347-360`, Variable `src_col`), gelesen aus
`pipes_timeseries.csv` (vom thermischen Netzwerk-Export erzeugt). Die Spaltenauswahl-Logik (`startswith("j1_to")`)
ist für ein generisches, numeriertes Knotenschema (`j1,j2,...j15`) geschrieben, nicht für Stadtbachs benannte Knoten
(`j_hkw`, `j_man`, ...) — der Fallback `sup_in_cols[0]` greift daher einfach die ERSTE `_T_supply_in`-Spalte in
Dateireihenfolge (empirisch: `ava_to_ost_T_supply_in`). **Wichtig (geprüft, kein Problem):** ALLE HKW-abgehenden
Rohre (`hkw_to_man`, `hkw_to_pss`, `hkw_to_psw`, `hkw_to_ost`) UND `ava_to_ost` zeigen exakt IDENTISCHE Werte
(84/96/99/115°C, 4 diskrete Stufen) — die Spaltenauswahl trifft also zufällig trotzdem die richtige, netzweit
einheitliche Erzeuger-Vorlauftemperatur, keine andere Erzeugerquelle.
Evidenz: `scripts/paper/extract_artefacts.py:347-360,441`; `output/exports/SB-S1-HK0/9be66307/thermal_network/pipes/pipes_timeseries.csv`.
Status: belegt

### A2b — Mit welcher Vorlauftemperatur rechnet die Netzphysik?
Antwort: **ZWEI unterschiedliche Repräsentationen derselben physikalischen Größe existieren im selben Lauf:**
1. **Kontinuierliche Heizkurve `T_VL_ts`** (`calion/utils/heizkurve.py:compute_heizkurve`, aufgerufen in
   `scenario_runner.py:373-385`): `T_VL(t) = clip(T_VL_min + k·(T_VL_max−T_VL_min)·(T_heiz−T_aus(t))/(T_heiz−T_aus,design), T_VL_min, T_VL_max)`,
   mit SB-HK0-Parametern `k=1.0, T_VL_min_c=70.0 (→floor-angehoben auf 75.0), T_VL_max_c=122.0` (`configs/paper_2/scenarios.yaml:55-59`).
   Diese Reihe treibt die Entlademaske.
2. **Diskretisierter Netzexport** (`T_supply_C`, s. A2a) mit nur 4 Werten (84/96/99/115°C) — vermutlich aus einem
   anderen, gröberen Berechnungspfad des thermischen Netzwerk-Exports/der Hydraulik-PWL-Approximation (NICHT im
   Detail nachvollzogen — Aufwand für vollständige Klärung: mittel, würde `calion/io/thermal_network_exporter.py`
   und die PWL-Druckverlust-Blöcke erfordern).
3. Der feste Konfigurationswert `supply_temp_c: 99.0` (`Stadtbach_topo.yaml:87`) existiert ZUSÄTZLICH — **vermutet**
   ein Hydraulik-Auslegungswert (Pumpendimensionierung o.ä.), nicht direkt in beiden obigen Reihen wiedergefunden
   (99°C ist aber zufällig einer der 4 diskreten Stufenwerte).
**Eigene Rekonstruktion von `T_VL_ts`** (reine Offline-Rechnung mit der echten `outdoor_temp_C`-Reihe aus
`data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx` und der obigen Formel): ergibt **2.033 Stunden > 95°C**
— gegen den Logwert **2.025** eine Abweichung von nur 8 h (0,4%), womit die Formel/Parameter als korrekt bestätigt
gelten (kleine Restabweichung vermutlich durch nicht-bit-exakte Reproduktion der internen Zeitreihen-Indizierung).
Status: belegt (Formel+Parameter, Codezeilen) + berechnet (Rekonstruktion, 99,6% Übereinstimmung mit dem Logwert)

### A2c — Entlädt der Speicher, obwohl die anliegende Temperatur > 95°C liegt? (für v7_final/SB-S1-HK0)
Mit der **exportierten** `T_supply_C` (6.552 h, falsche/andere Größe, s. A2a/b): 2.020 von 2.289 Entladestunden
(88%) "verletzen" scheinbar die Grenze — das ist aber ein Scheinbefund, da `T_supply_C` nicht die maskenrelevante
Größe ist (s. A2b).
Mit der **rekonstruierten, echten** `T_VL_ts`: **38 von 2.289 Entladestunden (1,7%)** fallen zusammen mit
`T_VL_ts > 95°C`. Gegeben die 8-Stunden-Restabweichung meiner Rekonstruktion gegenüber dem exakten Logwert (A2b),
liegen diese 38 Stunden wahrscheinlich im Rand-/Rundungsbereich um die 95°C-Schwelle und sind **eher ein Artefakt
meiner nicht-bit-exakten Rekonstruktion als eine echte Verletzung einer harten Modell-Constraint** — bei einer
harten `discharge[t] ≤ mask[t]·M`-Constraint im Pyomo-Modell wäre eine echte Verletzung unmöglich. **Nicht
abschließend widerlegt, da ich die echte modellinterne `T_VL_ts`-Reihe nicht direkt exportiert vorliegen habe,
nur meine eigene Rekonstruktion.**
Status: berechnet, mit explizit offener Restunsicherheit

### Fazit A2
**Physikalisch wahrscheinlich konsistent (ja, mit Vorbehalt)** — die Entlademaske nutzt nachweislich die
kontinuierliche `T_VL_ts`-Heizkurvenreihe (belegt durch Code + 99,6%-genaue Rekonstruktion), nicht die exportierte
`T_supply_C`-Spalte. Der ursprüngliche B2-M1-Befund (6.552 vs. 2.025 h) ist dadurch **aufgeklärt**: beide Zahlen sind
real, beschreiben aber ZWEI VERSCHIEDENE Größen, die denselben Spaltennamen-Anschein ("Vorlauftemperatur") erwecken.

**Meldepflicht A2-M2 (ersetzt B2-M1):** `dispatch_hourly.csv`s `T_supply_C`-Spalte ist NICHT die Heizkurven-/
Maskentemperatur, sondern ein strukturell anderer, diskretisierter Netzexport-Wert — dieser Namenskollision kann
jede künftige Validierung (wie meine eigene in B2) in die Irre führen. **Fixvorschlag:** entweder (a) `T_supply_C`
in `extract_artefacts.py` umbenennen (z.B. `T_supply_hydraulic_C`) und zusätzlich `T_VL_ts` selbst exportieren, oder
(b) dokumentieren, dass beide Größen bewusst getrennt sind und wofür jede gilt. Aufwand: klein (Spalten-Rename +
einen Export hinzufügen).

---

## A1 — Erratum zu A3c/A3d (Tranche 1): korrigierte Umpreisung mit TES-O&M

### A1a — Maximale spaltenweise Abweichung `dispatch_hourly.csv` ×0,5/×0,7/×1,3/×1,5 gegen ×1,0
**Bestätigt und noch eindeutiger als vermutet: die Abweichung ist NULL (reines Gleitkomma-Rauschen).**
Maximale absolute Differenz über ALLE Spalten, für alle vier Läufe gegen `v7_final/SB-S1-HK0`: **7,1×10⁻¹⁵**
(Spalte `Q_gasboiler_MW`, reines Float-Rundungsrauschen). Der Dispatch ist **bit-identisch** — nicht nur die
TES-Größe, sondern buchstäblich jede einzelne Dispatch-Entscheidung über alle 8.760 Stunden ist exakt dieselbe wie
im ×1,0-Lauf.
Evidenz: direkter Spalten-für-Spalten-Vergleich, Skript siehe unten.
Status: belegt

### A1b — Erratum als eigener Abschnitt

**Korrigierte Umpreisungs-Formel:** `T = T_CAPEX + T_OM = 354.000 + 27.209 = 381.209 EUR/a` je c0-Einheit
(`T_OM` aus `B1_kostenzerlegung.csv`: `OM_fixed_cost_EUR` bei ×1,0/×0,5/×0,7 = 1.581.726,64 / 1.568.122,05 /
1.573.563,89 -> Steigung 27.209,2 EUR/a je c0-Einheit, von mir in Tranche 1 fälschlich als TES-unabhängig
behandelt — tatsächlich ist die 0,5%-O&M-Pauschale auf die CAPEX bezogen und skaliert daher GENAUSO mit c0 wie
die CAPEX selbst).

| c0 | Umgepreist (korrigiert) | Real (Lauf) | Delta |
|---|---|---|---|
| 0,5 | 22.981.415,01 | 22.981.415,31 | **+0,30 EUR** |
| 0,7 | 23.057.656,81 | 23.057.656,99 | **+0,18 EUR** |
| 1,3 | 23.286.382,21 | 23.286.382,04 | **−0,17 EUR** |
| 1,5 | 23.362.624,01 | 23.362.623,72 | **−0,29 EUR** |

Alle vier Läufe treffen die korrigierte Umpreisung auf **unter 40 Cent** (vorher, mit der fälschlich
O&M-freien Formel, hatte ich 7.362-13.605 EUR "Abweichung" berichtet und daraus fälschlich auf echte
Dispatch-Unterschiede geschlossen). Status: berechnet, Eingangswerte belegt.

**Korrigierte Lesart (ersetzt meine A3c/A3d-Aussagen aus Tranche 1):** Keiner der vier Läufe (×0,5/0,7/1,3/1,5) hat
den Warmstart je verlassen (A1a bestätigt das jetzt auch für Dispatch, nicht nur Zielwert). **H5 ist damit
WIDERLEGT** — ×1,3/×1,5 sind NICHT schlechter als eine zulässige Lösung, sie SIND exakt die triviale Umpreisung
derselben S1-Lösung, auf 40 Cent genau. Ebenso sind ×0,5/×0,7 NICHT "echt besser" (meine Tranche-1-Aussage "real
BESSER als Umpreisung, Solution count 1 ist hier kein Rotes Tuch" war durch die fehlende O&M-Komponente verzerrt
— mit korrigierter Formel liegt auch hier kein Unterschied vor). **Die einzige Erkenntnis aus allen fünf Läufen
(×0,5/0,7/1,0/1,3/1,5) ist die CAPEX-Formel selbst** (bereits in A3b bestätigt) — keiner davon enthält eine
unabhängige Information über eine andere TES-Größe. Nur ×2,0 (`Solution count 10`, echte Exploration, Größe
fällt auf 37 MWh) bleibt als einziger unabhängig re-optimierter Punkt jenseits von ×1,0.

**Folge für §4cn-Elastizität:** bereits korrekt auf NUR ×1,0 und ×2,0 beschränkt — bleibt unverändert richtig,
jetzt aber mit einer saubereren Begründung (nicht "×1,3/1,5 könnten unterkonvergiert UND schlechter sein", sondern
"×1,3/1,5 sind nachweislich dieselbe Lösung, tragen keine zusätzliche Information").

**Break-even Altmodell (korrigiert):** `c0_breakeven = 1 + (PIN0_obj − S1_obj) / T = 1 + (23.370.804,48 −
23.172.019,51) / 381.209 = 1,5215` (statt c0≈1,56 mit der alten, O&M-freien Schätzung). In spezifischen Kosten
(Formel `spez(V,mult) = mult·250·(V/v0)^(b−1)`, V=30.379,4 m³, v0=10.000, b=0,7): **272,5 EUR/m³** (statt 280
EUR/m³ aus der alten Schätzung) — der Break-even liegt leicht UNTER dem ursprünglich berichteten Wert.
Status: berechnet (Formel + Eingangswerte belegt).

---

## B2 — Maskenstunden je Heizkurve (Kernfrage)

### B2a — Gesperrte Stunden je Netz × HK-Stufe (mit der echten T_aus-Reihe)

| Netz-HK | Maximales T_VL [°C] | Gesperrte Stunden | Anteil | Auftrags-Schätzung (zum Vergleich) |
|---|---|---|---|---|
| SB-HK0 | 120,84 | **2.033** | 23,2% | <2,0°C-Schwelle; Log-Realwert 2.025 (99,6% Treffer) |
| SB-HK1 | 109,59 | **616** | 7,0% | <−2,8°C-Schwelle |
| SB-HK2 | 96,37 | **15** | 0,2% | <−10,4°C-Schwelle; T_VL,max≈97,2°C behauptet, real 96,37°C |
| MM-HK0 | 98,56 | **112** | 1,3% | <−6,8°C-Schwelle |
| MM-HK1 | 92,67 | **0** | 0,0% | "nie", max. 94,0°C behauptet — **bestätigt (nie), Zahlenwert leicht abweichend** |
| MM-HK2 | 85,27 | **0** | 0,0% | "nie", max. 86,4°C behauptet — **bestätigt (nie), Zahlenwert leicht abweichend** |

**Die analytischen Schwellen aus dem Auftrag sind in der GRÖSSENORDNUNG und RICHTUNG bestätigt** (SB-HK0 deutlich,
HK1 wenig, HK2 fast nie blockiert; MM-HK1/HK2 nie blockiert), mit kleinen numerischen Abweichungen (einige
Prozentpunkte bei den absoluten Maximalwerten) — vermutlich durch geringe Unterschiede in der verwendeten
T_aus-Reihe oder Rundung, nicht durch einen Formelfehler (SB-HK0s Rekonstruktion trifft den LOG-Realwert auf 0,4%).
Evidenz: eigene Rekonstruktion mit `calion/utils/heizkurve.py:compute_heizkurve` + echten `outdoor_temp_C`-Reihen
aus `data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx` und `data/Import_Data_Memmingen_epronet_cleaned.xlsx`.
Status: berechnet (Formel belegt, Eingangsreihen belegt, Kalibrierung gegen Log-Realwert bestätigt)

### B2b — Überlappung mit Gaskessel-/EK-Betrieb im PIN0-Lauf (nur SB-HK0, 2.033 gesperrte Stunden)

- PIN0-Gaskesselbetrieb INNERHALB der gesperrten Stunden: **765 von 2.033 Stunden (37,6%)**, **28.472,7 MWh**
  (= 48,1% der PIN0-Gesamtjahresenergie des Gaskessels, 59.245,8 MWh).
- PIN0-EK-Betrieb innerhalb der gesperrten Stunden: **158 von 2.033 Stunden (7,8%)**, **1.285,0 MWh** (=24,2% der
  PIN0-EK-Jahresenergie).
- Mittlerer Bezugspreis in gesperrten Stunden: **114,15 EUR/MWh** vs. 89,18 EUR/MWh im Jahresmittel (+28%) —
  gesperrte Stunden fallen überproportional mit teuren, nachfragestarken Winterstunden zusammen (mittlere
  Netzlast 125,9 MW vs. 73,1 MW im Jahresmittel, +72%).
Evidenz: `output/v7_final/SB-S0-HK0-PIN0/dispatch_hourly.csv`, `economics.csv`.
Status: berechnet

### B2c — Obere Abschätzung des Zusatzwerts (Methode offengelegt)

**Methode (bewusst einfach, als obere Schranke, keine echte Re-Optimierung):** (1) gesperrte Stunden in
zusammenhängende Blöcke gruppieren (96 Blöcke, Median 10h, längster 193h/8 Tage); (2) je Block das MINIMUM aus
(a) der TES-Energiekapazität (438 MWh, Altmodell) und (b) der tatsächlich im Block von Gaskessel+EK erzeugten
Wärmemenge nehmen (= maximal verdrängbare Energie, wenn der Speicher den ganzen Block über mit voller Kapazität
genau dafür bereitstünde — eine ÜBERSCHÄTZUNG, da Aufladen zwischen den Blöcken und reale Leistungsgrenzen
ignoriert werden); (3) mit einem Vermeidungskosten-Satz bewerten.
**Ergebnis:** verdrängbare Energie über alle 96 Blöcke (gedeckelt): **14.551,6 MWh/a**. Vermeidungskosten-Satz:
NICHT sauber isolierbar aus den verfügbaren Exportdaten (PIN0s `(cost_fuel_eur+cost_co2_eur)/gas_consumption_MWh`
= 506,82 EUR/MWh ist eine GROBE, zu hohe Schätzung, da sie KWK-Gas (das auch Strom erzeugt) mit einschließt, nicht
nur Gaskessel-Gas). **Obere Schranke (sehr grob, mit explizit überschätztem Kostensatz):**
14.551,6 MWh × 506,82 EUR/MWh ≈ **7,4 Mio. EUR/a** — das ist eine BEWUSST zu hohe Zahl (Methode überschätzt sowohl
die verdrängbare Menge als auch den Kostensatz) und NICHT als belastbare Schätzung zu verwenden, sondern nur um
die Größenordnung einzugrenzen (sie liegt deutlich über dem bestehenden TES-Gesamtwert aus Tranche 1,
165-230 Tsd. EUR/a — ein Hinweis, dass die Maske keine marginale Einschränkung ist, sondern eine der
dominanten Werttreiber sein könnte, WENN sie aufgehoben würde).
Status: berechnet, explizit als grobe obere Schranke gekennzeichnet (keine echte Re-Optimierung ersetzt dies)

**Entscheidungsrelevanz für Teil C:** Angesichts der Größenordnung (obere Schranke >> bestehender TES-Wert) lohnt
sich ein echter C1/C2-Lauf (HK2 bzw. Maske-aus) methodisch klar — die grobe Schranke allein kann aber die exakte
Zahl nicht liefern, nur die Richtung rechtfertigen.

---

## B5 — Hot-Charging

### B5a — Lädt nur die WP heiß, oder auch KWK/Kessel?
**Nur die WP.** Die Kopplung ist eine HARTE GLEICHHEITS-Constraint `Qc(t) == Q_hot(t)` ausschließlich zwischen der
WP (`Q_hot`-Kanal) und dem TES-Ladeeingang (`calion/models/component_assembler.py:591-617`,
`_finalize_couplings`/`hot_charge_eq`). KWK, Biomassekessel und Gaskessel haben KEINEN Zugang zu dieser
Ladeschnittstelle — wenn die Kopplung aktiv ist (nur S3), kann der TES-Ladeeingang NUR aus der WP gespeist werden
(Sicherheitsmechanismus bei fehlender Kopplung: `qc[t]==0`, Zeile 609-610, verhindert sogar "kostenlose Energie"
falls die Kopplung aus irgendeinem Grund nicht gebaut wird).
Evidenz: `calion/models/component_assembler.py:591-617`.
Status: belegt

### B5b — Fließt die Hot-Ladung über die DN400-Leitung (j_hkw→j_man)?
**Nein — und das ist bei korrigierter Standort-Prämisse (s. Widerspruch oben) auch richtig so.** Die Kopplung
"umgeht den Knoten-Bus" (`component_assembler.py:1512`, `"[HOT-CHARGE] %s: Qc bypasses node bus"`) — sie ist eine
DIREKTE Pyomo-Gleichheits-Constraint zwischen zwei Variablen, OHNE jede Rohrleitungs-/Hydraulik-Beschränkung.
Das wäre ein Problem, WENN WP und Tank an verschiedenen Knoten lägen (wie im Auftrag angenommen) — tatsächlich
liegen in S3 BEIDE am selben Knoten j_man (s. Widerspruch oben), es gibt also physisch GAR KEINE Leitung
dazwischen, die zu umgehen wäre. Die Modellvereinfachung ist für S3 **korrekt**, nicht fehlerhaft.
Temperatur/Kappe: die Hot-Ladung läuft mit `T_charge=95°C` (atmosphärische Deckeltemperatur) und unterliegt
derselben `cap_power_MW`-Grenze wie normales Laden (keine separate Kappe für den Hot-Pfad gefunden).
Status: belegt (Kopplungsmechanismus) + berechnet (Konsequenz der korrigierten Standort-Prämisse)

### B5c — Gilt die 35-K-Spreizung für den GESAMTEN Speicherinhalt, auch bei KWK-Normaltemperatur-Ladung?
**Frage erübrigt sich — es gibt keine KWK-Ladung in S3.** Da (B5a) die Kopplung eine harte Gleichheit ist und
AUSSCHLIESSLICH die WP laden kann, kann KWK/Biomasse/Kessel-Wärme in S3 NIE in den TES-Ladeeingang fließen — es
gibt also keine Mischtemperatur-Situation, vor der die Frage warnt. **Keine Meldepflicht nötig.**
Status: belegt (logische Folgerung aus B5a)

---

## B7 — Mechanismus SB-S1 (löst §4co "Arbitrage" vs. B2 "KWK-Glättung" auf)

**Befund: `lambda_sell_eur_MWh` ist bei `v7_final/SB-S1-HK0` DURCHGÄNGIG 0,0 für alle 8.760 Stunden, UND
`P_chp_el_MW` ist ebenfalls durchgängig 0,0.** D.h. in diesem Lauf/Export gibt es GAR KEIN beobachtbares
KWK-Stromerlös-Preissignal (die 11,6 Mio. EUR `revenue_sell_eur` in `economics.csv` kommen aus einer anderen,
nicht stündlich aufgelösten Berechnung — vermutlich ein fixer Jahrespreis oder ein anderer Erzeuger/Strompfad, NICHT
aus dieser Spalte). **Eine "Lade nach KWK-Strompreis"-Arbitrage ist mit diesen Daten gar nicht testbar, weil das
Preissignal für diesen Mechanismus hier nicht existiert.**
Als Ersatzgröße geprüft: `lambda_buy_eur_MWh` (Bezugspreis, Median 92,92 EUR/MWh, Spanne −212,82 bis 473,28): nur
**916 von 1.561 Ladestunden (58,7%)** liegen über dem Median — eine schwache, kaum über Zufallsniveau liegende
Tendenz, und zudem in die "falsche" Richtung für eine Billig-Lade-Strategie (Preisarbitrage würde Laden
BEVORZUGT UNTER dem Median erwarten lassen, nicht leicht darüber).
Entladung vs. PIN0-Gaskesselbetrieb: **1.323 von 2.289 Entladestunden (57,8%)** fallen mit PIN0-Gaskesselstunden
zusammen (PIN0 hat insgesamt 2.316 Gaskesselstunden) — ein MODERATER, aber nicht vollständiger Zusammenhang.
Evidenz: `output/v7_final/SB-S1-HK0/dispatch_hourly.csv` (Spalten `lambda_sell_eur_MWh`, `P_chp_el_MW`,
`lambda_buy_eur_MWh`), `output/v7_final/SB-S0-HK0-PIN0/dispatch_hourly.csv` (`Q_gasboiler_MW`).
Status: belegt

**Fazit (ein Satz mit Zahlen):** Die Daten widerlegen eine Strompreis-Arbitrage-Erklärung (§4co) — das dafür nötige
KWK-Erlös-Preissignal existiert in den Exportdaten gar nicht (`lambda_sell≡0`), und der schwache
Bezugspreis-Zusammenhang (58,7%) zeigt KEINE klare Billig-Lade-Präferenz; stattdessen stützen die vorhandenen
Daten die B2-Lesart ("KWK-Glättung + Gasboiler/EK-Verdrängung") aus Tranche 1 (`corr_charge_vs_chp=0,60`,
Gasboiler −32% Betriebsstunden) mit einem moderaten (58%) Entlade/Gaskessel-Zeitüberlapp als zusätzlichem Beleg.

---

## A3 — Gebaute Leistungen (EK-Kapazität je Lauf, WP/EK-Standorte)
*(Hinweis: im Auftrag als "A3" in Teil A benannt, Tabellenname "B3b" vom Auftrag selbst so vorgegeben — Reihenfolge-Label
"B3" in der Ablieferungsreihenfolge ist vermutlich ein Tippfehler für "A3", da Teil B keine eigene B3-Frage enthält.)

**EK-Kapazität (investierbarer `EK_SB`, aus `full_solution_dump.json`, Variable `EK_SB_cap_mw`/`EK_SB_build`):
0,0 MW in ALLEN drei geprüften SB-Läufen (S1, S2, S3) — die EK wird NIE investiert, egal am Standort.** Das
schließt den in Tranche 1 offen gelassenen Punkt (A2d) ab: die dort beobachtete `Q_ek_MW`/`P2H_MW`-Dispatch
(identisch 9,9 MW über S1/S2/S3) kommt vom SEPARATEN, NICHT-investierbaren Bestandsasset `p2h_existing`
(`Stadtbach_topo.yaml:151`, eigener Eintrag neben `ek_sb` in der Asset-Liste), NICHT vom investierbaren `EK_SB`.
HP-Kapazität (`hp_sb_cap_mw`, bestätigt identisch zu meiner Tranche-1-Dispatch-Max-Schätzung): S1=2,506 MW,
S2=1,840 MW, S3=1,848 MW (alle `build=1`).
MM: `hp_main_cap_mw=0,0 (build=0)` — die investierbare WP wird in MM-S1 NICHT gebaut; `EBOILER_MAIN_cap_mw=0,103
MW (build=1)` — eine sehr kleine EK wird gebaut.
Tabelle: `v6/tables/B3b_bau_entscheidungen.csv`.
Evidenz: `output/{v7_final/SB-S1-HK0,_s2/sb_s2_resolve2/.../SB-S2-HK0,_s2/sb_s3_resolve/.../SB-S3-HK0,v7_final/MM-S1-HK0}/full_solution_dump.json`.
Status: belegt

**WP/EK-Standorte (korrigiert, s. Widerspruch oben):** effektiv **j_man** für ALLE SB-Investitionsszenarien
(bestätigt über `_apply_hp_location`-Mechanismus + `scenarios.yaml hp_nodes`), **j_12** für MM (Basis-Config,
keine Verschiebung nötig, `Memmingen_P2_base.yaml:216`). Status: belegt

**Kopfkommentar-Doku-Defekt bestätigt:** `Stadtbach_topo.yaml` Zeile 11 ("investable HP (hp_sb) co-located at
j_ava") stimmt mit WEDER dem statischen Default (j_hkw, Zeile 151) NOCH der laufzeit-effektiven Position (j_man)
überein — ein veralteter Kommentar aus einer früheren Modellversion.
**Meldepflicht B3-M1:** Kopfkommentar in `Stadtbach_topo.yaml` korrigieren oder entfernen (Aufwand: trivial,
Ein-Zeilen-Kommentarfix).

---

## B8 — Heizkurve unter V7 (= B6 aus v5)

**Wurde HK1/HK2 unter V7 oder im neuen Modell je gerechnet? NEIN, nicht für die Investitions-/TES-Wert-Szenarien
(S1/S2/S3).** Alle auffindbaren `HK1`/`HK2`-Läufe für SB liegen unter `output/exports/_quarantine/` (z.B.
`SB-S6-HK1__hp_*__tes_*`, `SB-S6-HK2__hp_*__tes_*`) — das sind QUARANTÄNE-markierte Artefakte einer FRÜHEREN,
ANDEREN Studie (S6 = endogene Siting-Kombinatorik aus der F3-Siting-Phase, nicht S1/S2/S3). MM hat
`exports/MM-S0-HK2`/`MM-S2-HK2`, ebenfalls S0/S2 (Baseline/Sitingstudie), nicht S1 (frei, investierbar).
**Für keinen der aktuell berichteten S1/S2/S3-TES-Wert-Läufe existiert ein gültiger HK1- oder HK2-Lauf.**
Evidenz: `find output -iname "*HK1*"/"*HK2*"` (Verzeichnisliste oben, Dateipfade mit `_quarantine`).
Status: belegt

**Worauf stützt sich "Heizkurve ≤0,1%"?** Auf `MODEL_AND_DOE_CONTROL.md:1069`: "Heizkurvenhebel SB **−0,08%
Kosten, +0,12% CO₂**" — das ist ein Vergleich **BC-SB (FIX, konstante Vorlauftemperatur) vs. BC-SB-HK0**, eine
REINE BASELINE-Studie (kein Investment, `D3`-fixierte Kapazität) aus einer FRÜHEREN, ANDEREN Fragestellung
("H*": war die Heizkurve ein 20%-Elektrifizierungshebel? — widerlegt). **Das ist NICHT HK1-vs-HK2 und NICHT der
Investitions-/TES-Kontext** — die 0,1%-Zahl beantwortet eine andere Frage als die hier gestellte.
Evidenz: `docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md:1069`.
Status: belegt

**Welche Kanäle würde HK2 in SB bewegen, wie groß offline?**
- **Maskenstunden (B2a, berechnet, größter Hebel):** HK0=2.033h (23,2%) → HK2=15h (0,2%) — eine Reduktion um
  **99,3%** der blockierten Stunden. Das ist der GRÖSSTE der vier Kanäle und bereits quantitativ belegt.
- **ΔT_TES (B1, berechnet):** UNVERÄNDERT bei 15,0K für HK0 UND HK2 (Floor-Konstruktion, siehe B1) — dieser Kanal
  bewegt sich NICHT. Eine gleich große TES-Volumen-Investition hätte bei HK2 also dieselbe Energiekapazität wie
  bei HK0.
- **WP-COP (vermutet, Richtung plausibel, Betrag nicht quantifiziert):** HK2 hat niedrigere Vorlauftemperaturen
  (T_VL,max≈96,4°C vs. 120,8°C bei HK0, B2a) — ein niedrigerer Hub von der ~41,7°C-Abwärmequelle (B6) auf ein
  niedrigeres Zielniveau sollte den COP VERBESSERN (höher), die genaue COP-Formel des Modells wurde für diese
  Abschätzung nicht nachvollzogen (Aufwand: klein, ein Blick in die COP-Precompute-Funktion würde reichen).
- **Netzverluste (vermutet, Richtung plausibel):** niedrigere Netztemperatur → geringere ΔT zur Umgebung → tendenziell
  geringere Wärmeverluste (`Q_loss_total_MW`-Spalte vorhanden, aber nicht zwischen HK-Stufen vergleichbar, da kein
  gültiger HK2-S1-Lauf existiert, s.o.).
Status: B2a/B1-Kanäle belegt+berechnet, COP/Netzverlust-Kanäle vermutet (Richtung) ohne quantifizierten Betrag.

---

## A4 — Ursache `output/_s2/sb_s2_resolve/.../SB-S2-HK0` (ungültig)

**Ein Satz:** Der direkte Warmstart-Transplant von S1s Lösung (TES an j_hkw) auf S2 (TES-Kandidat an j_man)
verletzte eine Modell-Constraint (`"User MIP start violates constraint c_e_x16012581_ by 18.109369869"`,
`chain.output:669`), wodurch Gurobis SubMIP-Reparatur einen minderwertigen, kaum konvergierten Start erzeugte
(`obj_eur=45.916.707,27`, Gap 49,31%, `build=1` mit nur 37 MWh an j_man) — behoben in `sb_s2_resolve2` durch
Warmstart vom PIN0-Dump (`CALION_WARMSTART_DUMP`+`CALION_SEED_FILL_ZERO=1`) statt direkt von S1.
In `B4_konvergenz_provenienz.csv` (Tranche 1) bereits mit `notes="FAILED Versuch, superseded by *_resolve2"`
markiert — hiermit zusätzlich explizit bestätigt als "ungültig" für `v6`.
Status: belegt

---

## B6 — Wärmequelle der WP (`WRG1Q_MW`)

**Statistik (SB, aus `data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx`):** Max=11,73 MW, Mittel=7,84 MW,
P95=11,13 MW, Jahresenergie=68.684 MWh, Stunden>0=8.760/8.760 (**durchgängig verfügbar, nie null**).
Quelltemperatur `WRG_1_Celsius`: Min/Mittel/Max = 36,45 / 41,71 / 44,65°C (konstant niedrige Abwärme, passend zu
einem COP-Anheber: `Precomputed COP: mean=3,26, min=2,45, max=3,73` für `hp_sb`, bereits aus früheren Logs belegt).
Evidenz: `data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx` (Spalten `WRG1Q_MW`, `WRG_1_Celsius`).
Status: belegt

**Begrenzt die Quelle die gebaute WP-Größe (SB 1,4-2,5 MW)? NEIN.** Die maximale Abwärmequelle (11,73 MW) ist
**4,7× größer** als die größte gebaute WP (S1: 2,506 MW) — die Wärmequelle ist in keinem der geprüften Läufe
der limitierende Faktor; die WP-Investitionsgröße wird wirtschaftlich (CAPEX vs. Nutzen), nicht durch
Quellenverfügbarkeit, bestimmt.
Status: berechnet (Verhältnis aus zwei belegten Werten)

**WP-Anteil an der Jahreswärme je Lauf** (`share_HP_pct`, `economics.csv`, bereits aus Tranche 1 bekannt):
S1=1,35%, S2=1,05%, S3=1,07% — durchgängig klein, konsistent mit der kleinen absoluten WP-Größe relativ zum
Gesamtnetz (SB-Spitzenlast ~200+ MW).
Status: belegt

---

## B1 — Spreizung: ΔT_TES = 15K bestätigen

**Bestätigt für alle 6 Kombinationen (SB/MM × HK0/HK1/HK2), per Formel + realen Config-Werten:**

`delta_T_scenario_k = round(T_VL_min_effective − T_return, 2)` (`scripts/paper_2/scenario_runner.py:451`, einziger
Berechnungsort, ein Skalar pro Szenario — NICHT zeitabhängig, NICHT vom ladenden Erzeuger abhängig). Mit
`T_VL_min_effective = max(T_VL_min_c, T_return + min_supply_delta_T_k)` (`min_supply_delta_T_k=15,0` für BEIDE Netze,
`Stadtbach_topo.yaml:90`, `Memmingen_P2_base.yaml:101`):

| Netz | HK | T_VL_min_c (config) | T_return (`T_RL_c` falls gesetzt, sonst Basis) | T_VL_min_effective | ΔT_TES |
|---|---|---|---|---|---|
| SB | HK0 | 70,0 | 60,0 (Basis) | max(70; 75)=**75,0** | **15,0** |
| SB | HK1 | 65,0 | 50,0 (`T_RL_c`) | max(65; 65)=**65,0** | **15,0** |
| SB | HK2 | 60,0 | 45,0 (`T_RL_c`) | max(60; 60)=**60,0** | **15,0** |
| MM | HK0 | 74,0 | 63,6 (Basis) | max(74; 78,6)=**78,6** | **15,0** |
| MM | HK1 | 70,0 | 55,0 (`T_RL_c`) | max(70; 70)=**70,0** | **15,0** |
| MM | HK2 | 66,0 | 51,0 (`T_RL_c`) | max(66; 66)=**66,0** | **15,0** |

Alle sechs treffen exakt 15,0 K — **per Konstruktion** (die 15K-Flooring-Regel bindet in JEDEM Fall, mal über
`T_VL_min_c` direkt, mal über die `+15K`-Anhebung; die HK1/HK2-`T_RL_c`-Werte wurden erkennbar genau so gewählt,
dass der Floor bindet). Evidenz: `scripts/paper_2/scenario_runner.py:451`, `configs/paper_2/scenarios.yaml:30-71`,
`Stadtbach_topo.yaml:88,90`, `Memmingen_P2_base.yaml:94,101`.
Status: belegt

**Abhängigkeit vom ladenden Erzeuger oder von T_VL(t)?** NEIN für den normalen (Kalt-)Lademodus — `delta_T_scenario_k`
ist ein EINZIGER Skalar pro Szenario, berechnet einmal vor dem Solve, nicht pro Zeitschritt oder Erzeuger. Die EINZIGE
Ausnahme ist der Hot-Charging-Modus (S3): dort gilt ein ANDERES, ebenfalls fixes ΔT=35K (`T_charge=95°C − T_return`,
siehe `chain.output`-Zitat "HOT CHARGING: T_charge=95.0 degC, TES dT=35.0 K").
Status: belegt

**Hydraulische Kappe 51,8 MW nutzt ebenfalls ΔT=15K:** bestätigt, direkt aus dem Kommentar
`storage_geometry.yaml:252` (`"... P = m_dot * c_p * dT = 824 kg/s * 4.189 kJ/(kg K) * 15 K = 51.8 MW"`) — bereits
in B4 zitiert. Status: belegt

---

## B4 — Anbindung je Kandidatenknoten: Gilt die 51,8-MW-Kappe auch für j_man?

**Antwort: JA, die Kappe gilt uniform für JEDEN Standort — das ist ein bestätigtes Problem.**
`power_max_mw: 51.8` ist ein EINZIGER, standortunabhängiger Parameter des Asset-TYPS `tes_sb` in
`configs/paper_2/storage_geometry.yaml:256`, abgeleitet aus einer **angenommenen DN600-Leitung**
(`storage_geometry.yaml:250-253`: `m_dot=824 kg/s, c_p=4,189 kJ/kgK, ΔT=15K -> 51,8 MW`). Der Code liest ihn rein
aus der statischen Asset-Konfiguration (`component_assembler.py:1357-1358,1496-1497`,
`geometric_storage.py:178,184,433-434`) — es gibt KEINE Fallunterscheidung nach `tes_node` irgendwo im Code (geprüft:
`grep -rn power_max_mw` über `calion/` und `scenario_runner.py` zeigt nur die generische Asset-Config-Lesung und
einen global-skalaren Env-Override `CALION_TES_POWER_MAX`, ebenfalls nicht node-spezifisch).

**j_mans reale Anbindung ist aber DN400, nicht DN600:** `Stadtbach_topo.yaml:345-351` (`hkw_to_man`,
`diameter_mm: 400`) ist die EINZIGE Leitung nach j_man. Aus `pipes.csv` (A2-Tranche-1-Befund, erneut bestätigt):
`m_dot_max_kg_s=333,109` (nicht 824!). Bei ΔT=15K: `Q_max = 333,109 × 4,189 × 15 / 1000 ≈ 20,9 MW` — **weniger als
die Hälfte** der angenommenen 51,8 MW.

**Konsequenz:** Ein TES an j_man (S2/S3) dürfte im Modell mit bis zu 51,8 MW laden/entladen, obwohl die einzige
physische Leitung dorthin nur ≈20,9 MW trägt — der Standortvergleich S1 vs. S2 (Tranche 1, A2) bildet die
Netzhydraulik an S2 NICHT korrekt ab. **Das relativiert den S1-vs-S2-Befund nicht grundsätzlich** (S2 hatte sich
ohnehin für `build=0` entschieden — mit einer NOCH strengeren Kappe würde sich daran nichts ändern, S2 bliebe
unattraktiv), **aber es bedeutet, dass die Kappe bei S2 in die FALSCHE Richtung verzerrt** (zu großzügig, nicht zu
streng) — die Kappe allein erklärt S2s `build=0` also nicht, das Ergebnis ist eher noch robuster als es aussieht.

Evidenz: `configs/paper_2/storage_geometry.yaml:250-256`, `calion/models/component_assembler.py:1357-1358,1496-1497`,
`calion/models/blocks/geometric_storage.py:178,184,433-434`, `configs/paper_2/Stadtbach_topo.yaml:345-351`,
`output/_s2/sb_s2_resolve2/paper2_runs/SB-S2-HK0/pipes.csv` (Zeile `hkw_to_man`).
Status: belegt

**Meldepflicht B4-M1:** `power_max_mw` sollte node-/standort-spezifisch gesetzt werden (abgeleitet aus der
tatsächlichen Anbindungsleitung je `tes_node`), nicht als einziger Asset-Typ-Parameter. Betrifft alle
S2-S5-Standorte (unterschiedliche Rohrdurchmesser, siehe `tes_nodes`-Mapping in `scenarios.yaml`). Fixvorschlag:
in `scenario_runner.py` beim Aufbau von `_asset_cfg["power_max_mw"]` den Wert aus der tatsächlichen
Anbindungsleitung des aktuellen `tes_node` berechnen (Formel bereits vorhanden, nur die Quelle `m_dot_max_kg_s`
müsste pro Knoten statt pauschal 824 kg/s gelesen werden). Aufwand: klein-mittel (Formel existiert, nur die
Pipe-Lookup-Logik fehlt).

---

## Teil C — Laufvorschläge (NUR Aufwandsschätzung, NICHTS gestartet, kein `[x]`)

**Vorab: Laufzeit/RAM bei fixierter Investition.** Referenzpunkt (belegt, aus bereits gelaufenen Läufen):
`SB-S0-HK0-PIN0` (HP/EK noch frei, nur kein TES) löste in **13.805,65s (3,8h)**; `MM-S0-HK0-PIN0` in **514,6s
(8,6 min)** — beide ohne Nodefile-Spill-RAM-Probleme. Eine ECHT vollständig fixierte Dispatch-Variante (auch
HP/EK/TES-Größe und -Leistung fest, NUR Dispatch frei) sollte SCHNELLER sein als PIN0 (keine
Investitions-Binärvariablen mehr, nur Betriebs-Binärvariablen wie An/Aus) — **Schätzung (vermutet, nicht
gemessen): SB 10-60 Minuten, MM 2-10 Minuten**, RAM deutlich unter PIN0s bereits unkritischen Werten. C1-C4
könnten DAMIT teils als kurze Dispatch-Läufe statt 48h-MILPs laufen, wenn die Investitionsgrößen aus einem
Referenzlauf übernommen werden.

| # | Konfiguration | Referenzläufe nötig | Zeitschätzung | Position/Verdrängung |
|---|---|---|---|---|
| **C1** | SB-S1 neues Modell, Basispunkt AE/AF (c0×2,0, 25k€/MW), HK2 statt HK0, volle Investitionsfreiheit | PIN0-HK2 (neu), speicherfreie Referenz HK2 (neu) — **3 Läufe** | ~8h je Lauf (volles MILP) × 3 = **~24h**, parallelisierbar | Nach AG4-Warteschlange |
| **C2** | Wie C1, aber HK0 + `CALION_TES_NO_DISCHARGE_MASK=1` (Maske aus, obere Schranke) | Referenzen vermutlich schon aus der AE/AF-Kampagne vorhanden | ~8h (1 Lauf) | Nach AG4-Warteschlange |
| **C3** | TES an j_man, mit der nach B4 korrigierten (standortspezifischen, ≈20,9 statt 51,8 MW) Leistungskappe | Braucht zuerst den B4-M1-Fix ODER einen manuellen Env-Override — AKTUELL NICHT ohne Codeänderung möglich | ~8h, blockiert bis B4-M1 behoben | Blockiert |
| **C4** | MM Hot-Charging an j_12, mit speicherfreier Referenz | 1 Zusatzreferenz (evtl. schon vorhanden) | MM viel schneller als SB (PIN0-Referenz 514,6s) — **~1-3h** | Nach AG4-Warteschlange, geringer Ressourcenbedarf |

**Gesamt (vermutet):** C1(3 Läufe,~24h) + C2(1,~8h) + C4(1,~1-3h) ≈ **33-35h** bei paralleler Ausführung. C3
unabhängig blockiert bis B4-M1 umgesetzt ist. Keiner dieser Läufe wurde gestartet (kein `[x]`).

---

## Zusammenfassung / Stand

Alle Punkte aus Teil A (A1-A4) und Teil B (B1,B2,B3[=A3],B4,B5,B6,B7,B8) bearbeitet, Teil C nur als
Aufwandsschätzung (nichts gestartet). Wichtigste Befunde: (1) A2 löst den B2-M1-Namenskollisionsfund aus Tranche 1
vollständig auf (zwei verschiedene "Vorlauftemperatur"-Größen im selben Export); (2) A1 korrigiert meine eigene
Tranche-1-Aussage (H5 war ein Rechenfehler meinerseits, keine echte Unterkonvergenz-Entdeckung — die
O&M-Komponente fehlte in der Umpreisung); (3) B4 bestätigt eine neue, reale Meldepflicht (51,8-MW-Kappe gilt
fälschlich uniform für alle TES-Standorte); (4) zwei Auftragsprämissen (B3/B5: WP-Standort j_hkw) waren durch die
laufzeit-dynamische `_apply_hp_location`-Verschiebung überholt — korrigiert auf j_man, was B5 sogar von einer
vermuteten Meldepflicht zu einem bestätigt unproblematischen Befund macht.

**Hinweis zur Dateistruktur:** Die Abschnitte liegen in der Datei nicht exakt in der angeforderten Reihenfolge
(A2→B2→B4→A1→B1→B5→B7→A3→B6→B8→A4→C), da neue Abschnitte beim Schreiben jeweils vor dem zuletzt unbearbeiteten
Platzhalter eingefügt wurden. Inhaltlich sind alle Punkte vollständig; eine Umsortierung ist auf Wunsch schnell
nachträglich möglich.

**STOPP — wartet auf Rückmeldung.**
