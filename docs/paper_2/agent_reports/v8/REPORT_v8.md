# REPORT v8 — Modellkonsolidierung vor jedem weiteren Lauf (Agent-Auftrag v8, 2026-10-23)

Reihenfolge: A1 → A2 → A4 → A3 → A5 → B3 → B1 → B2.

## Widersprüche
Keine.

## Meldepflichten (neu, diese Runde)
- A1: j_man ist ein strukturell isolierter Verbrauchsknoten (siehe unten) — das ist die vermutlich FUNDAMENTALSTE
  Erklärung für S2/S3s `build=0`, nicht nur die Leistungskappe (B4) oder das falsch skalierte ΔT (s.u.).

## Korrekturen zu v7 (eigene Fehler, zurückgenommen)
- **H1/H2 ΔT-Fehler:** Ich hatte die Pipe-Kapazitätsrechnung (20,9 MW, 17,7 MW Restkapazität, 3,2 MW MAN-Spitze)
  mit 15K gerechnet — die Netzphysik nutzt aber `temperature_frame` (84-115°C Vorlauf, 60-62°C Rücklauf, also
  22-53K je Saison). **Neu gerechnet unten (A1).**
- **D1-Rechenfehler:** `5.439.000 / 438 = 12.418,26 EUR/MWh`, nicht "≈13.600" wie ich schrieb — einfacher
  Rechenfehler, danke für den Fang.
- **W2-Annahme falsch:** Biomasse (`BMHKW`) läuft in PIN0 bereits 8.760/8.760h (bestätigt in meiner eigenen
  Tranche-1-B2-Analyse, dort nicht weiterverfolgt) — es gibt KEINE freie Biomasse-Kapazität, die zusätzlich als
  "billige Ladequelle" dienen könnte. Der 70,79-EUR/MWh-Spread (Biomasse) ist daher keine gültige obere Schranke.

---

## A1 — Stichknoten j_man (hohe Priorität)

### A1a — Bestätigung am Code
**Bestätigt: `hkw_to_man` ist NICHT bidirektional.** `configs/paper_2/Stadtbach_topo.yaml:345-351` hat KEIN
`bidirectional`-Schlüssel → Default `False` (`calion/models/blocks/pipe_pair.py:170`:
`bidirectional = bool(physics_cfg.get('bidirectional', config.get('bidirectional', False)))`). Im
Nicht-bidirektionalen Zweig wird `m_dot` als `pyo.Var(..., domain=pyo.NonNegativeReals, bounds=(0,
effective_max_flow))` gebaut (`pipe_pair.py:302`) — Fluss NUR von `from: j_hkw` nach `to: j_man`, nie umgekehrt.
`j_man`s Knotendefinition (`Stadtbach_topo.yaml:189-191`) hat NUR `consumers: [MAN_MW]`, KEINE weiteren
Leitungen, KEINE anderen Erzeuger in der STATISCHEN Topologie (HP/EK werden erst zur Laufzeit dorthin verschoben,
v6.1 A3). **Es gibt einen LOKALEN Dump-Mechanismus an j_man** (`output/v7_final/SB-S1-HK0/dump_audit.json`:
Knoten `j_man` mit `n_nonzero_hours=270`, `max_mw=0,567`, `sum_mwh=51,27`) — Überproduktion wird NICHT hart
blockiert, sondern bei Bedarf klein dosiert verworfen.
Status: belegt

### A1b — Stündlicher Vergleich WP-Wärme vs. MAN-Last (`v7_final/SB-S1-HK0`, `SB-S2-HK0`, `SB-S3-HK0`)

| Lauf | hp_sb Jahres-MWh | hp_sb > MAN_MW [h] | hp_sb ≈ MAN_MW (±0,05 MW) [h] | hp_sb < MAN_MW [h] | hp_sb-Stunden>0 |
|---|---|---|---|---|---|
| S1 | 8.639,4 | 729 | 2.069 | 6.468 | 4.302 |
| S2 | 6.709,7 | 524 | 1.948 | 6.779 | 4.233 |
| S3 | 6.864,3 | 617 | 2.009 | 6.648 | 4.398 |

**MAN_MW-Statistik (echte Messreihe, `stadtbach_acron_combined_cleaned.xlsx`):** Mittel=2,02 MW, P5=0,01 MW,
P50=0,84 MW, P95=6,87 MW, Max=12,48 MW, **Sommermittel=0,25 MW** (praktisch keine Last im Sommer — passt zu
"MAN industrial waste heat", vermutlich ein saisonaler Industrieprozess). Jahresenergie MAN_MW: **17.719,9
MWh**.
**Überschuss-Analyse S1 (`hp_sb − MAN_MW > 0,01`):** 733 Stunden, mittlerer Überschuss 0,319 MW, Summe 233,8
MWh/a — davon werden laut Dump-Audit NUR 51,27 MWh tatsächlich am Knoten verworfen. **Rest (≈182 MWh) nicht
restlos aufgeklärt** (vermutlich EK_SB-Mitverbrauch am selben Knoten oder ein Mess-/Rundungs-Artefakt in meinem
Proxy-Vergleich — Aufwand zur vollen Klärung: klein, EK_SB-Dispatch mit einbeziehen).
Status: belegt (Tabelle, MAN-Statistik) + berechnet (Überschuss) + offen (182-MWh-Lücke)

### A1c — Folge für die Ergebnisse
**Gebaute WP-Größe durch MAN-Last erklärbar? JA, berechnet.** `hp_sb` liefert in S1 nur 8.639 MWh/a gegen
MAN_MWs 17.720 MWh/a Gesamtbedarf (48,8% Deckungsgrad) — die WP ergänzt, deckt aber nicht die volle Last (der
Rest kommt vermutlich über den Leitungszufluss von j_hkw, nicht separat verifiziert). Die Übereinstimmung
hp_sb≈MAN_MW in ~24% der Stunden (2.069-2.009 h je Lauf) UND die geringe Überschreitung (nur 729-524h, meist
kleine Beträge, größtenteils über den lokalen Dump abgefangen) stützen: **die WP-Größe ist weitgehend durch die
MAN-Last limitiert, nicht durch ihre eigene Investitionsökonomie allein.**
**Ist S2/S3 `build=0` strukturell erzwungen? Überwiegend JA, berechnet — und FUNDAMENTALER als B4s
Leistungskappe.** Ein TES an j_man (Sackgassen-Knoten, einseitige Leitung) kann NUR die lokale MAN-Last zeitlich
verschieben — es kann NIEMALS Energie Richtung j_hkw oder andere Netzteile zurückspeisen. Bei einer
Jahres-MAN-Last von nur 17.720 MWh (verglichen mit SB-Gesamtnetzlast von ~640 GWh/a, Memory-Referenz) ist das
ökonomische Potenzial eines Speichers an diesem Knoten VON VORNHEREIN auf eine winzige Nische begrenzt —
unabhängig von der (ohnehin zu hohen) 51,8-MW-Kappe aus B4. **Das ist eine wichtigere Erklärung für `build=0`
als die Leistungskappe.**
Status: berechnet (Ladebilanz) + vermutet (dass dies die DOMINANTE statt nur eine mitwirkende Erklärung ist —
ein Vergleich mit einem TES an einem NICHT-isolierten Knoten wie j_pss/j_psw wäre nötig, um das zu trennen)

### A1d — Gleiche Prüfung für MM j_12
**Nicht im Detail durchgeführt (Zeitgründe) — nur die strukturelle Vorprüfung:**
MMs `j_12` ist STRUKTURELL ANDERS als SBs `j_man`: `Memmingen_P2_base.yaml:212-222` zeigt `j_12` mit **drei
eigenen Verbrauchern** (`V_19/20/21_demand_MWth`, nicht nur einem) UND **mindestens zwei Rohrverbindungen**
(eine `from: j_12` Zeile 284, eine `to: j_12` Zeile 334 — zu unterschiedlichen Nachbarknoten, Kommentar
Zeile 258-259: "j_4 subtree now hangs off j_12") — j_12 ist ein DURCHGANGS-Knoten mit einem eigenen Teilbaum,
kein Sackgassen-Knoten wie j_man. **MM ist daher vermutlich NICHT auf dieselbe Weise strukturell isoliert wie
SBs j_man** — allerdings erklärt das NICHT, warum MM in S1 ohnehin `hp_main_build=0` zeigt (v6.1 A3) — dort ist
die Erklärung vermutlich rein ökonomisch (WP lohnt sich an diesem Standort nicht), nicht topologisch.
Status: belegt (Topologie-Unterschied) + vermutet (dass dies die alleinige Erklärung für MMs eigenes
Nicht-Bauen ist — nicht vertieft, Aufwand für volle Parität mit A1a-c: mittel)

---

## A2 — Messdaten

### A2a — Weitere Messreihen
**Rücklauf-Messreihe (HKW) EXISTIERT:** `data/Stadtbach/11_Messwerte_Acron/HKW/HKW_Temp_RL.xlsx` (stündlich,
2025). Statistik: **Min=35,4°C, Mittel=61,53°C, Max=72,5°C** — Mittel liegt nah am Modell-Rücklaufwert (60°C),
aber die reale Streuung (35,4-72,5°C) ist erheblich, KEIN fester Wert.
PPS/PSW haben ebenfalls `_Temp_VL.xlsx`/`_Temp_RL.xlsx` (gefunden in A1-Exploration, nicht ausgewertet —
Aufwand: klein, identische Methode wie HKW).
**MM: KEINE vergleichbaren Messreihen gefunden.** Nur `Import_Data_Memmingen_epronet_cleaned.xlsx` (Modell-
Eingangsdaten: `outdoor_temp_C`, Verbraucher-`V_n_flow_temp`/`_return_temp` PRO TRANSFERSTATION, aber keine
zentrale Erzeuger-Vorlauftemperatur wie SBs HKW-Messung). MM-Kalibrierung (A2b) daher NICHT durchführbar mit
denselben Mitteln.
Status: belegt

### A2b — Kalibrierung `compute_heizkurve` per Kleinste-Quadrate (SB, gegen `HKW_Temp_VL.xlsx`)
**Ergebnis:** `k=0,994` (praktisch exakt 1,0 — stützt HK0s Annahme k=1,0), **`T_VL_min=92,35°C`** (MASSIV höher
als die Modellannahme 70-75°C!), `T_VL_max=119,94°C` (nah an der Modellannahme 122°C). **R²=0,743, RMSE=3,81°C.**
**Stunden>95°C der kalibrierten Kurve: 5.924 von 8.758 (67,6%)** — das liegt VIEL näher an der echten Messung
(4.974h, 56,8%) als sowohl `T_VL_ts` (2.033h, 23,2%) als auch `temperature_frame` (6.552h, 74,8%).
Evidenz: `scipy.optimize.curve_fit` gegen `calion/utils/heizkurve.py:compute_heizkurve`, echte `outdoor_temp_C`
und `HKW_Temp_VL.xlsx`.
Status: berechnet (echte Kalibrierung, keine Schätzung)

**Kernbefund:** Die aktuelle Modell-Heizkurve (`T_VL_min_c=70°C`) ist GEGENÜBER DER REALITÄT (kalibriert:
92,35°C) massiv unterkalibriert — der Boden liegt real >20K höher. **Das stützt E1 (Messungs-kalibrierte
Heizkurve als neue Basis) mit einer konkreten, direkt verwendbaren Zahl.**
MM: nicht kalibrierbar (A2a).

### A2c — Wie gut trifft `temperature_frame` die Messung?
**RMSE gesamt: 7,56°C** (schlechter als die kalibrierte Kurve mit 3,81°C — erwartbar, da `temperature_frame`
nur 4 feste Saisonwerte statt einer kontinuierlichen Kurve hat).

| Saison | RMSE [°C] | Stunden>95°C in der ECHTEN Messung | Anteil |
|---|---|---|---|
| Winter (115°C-Annahme) | 7,56 | 2.160/2.160 | **100,0%** |
| Frühling (99°C-Annahme) | 4,81 | 1.111/2.207 | **50,3%** |
| Sommer (84°C-Annahme) | 9,37 | 179/2.208 | **8,1%** |
| Herbst (96°C-Annahme) | 7,80 | 1.524/2.183 | **69,8%** |

**Einordnung:** Winter trifft `temperature_frame`s Annahme (immer heiß) gut. Sommer ist am UNGENAUESTEN (höchste
RMSE) — `temperature_frame` nimmt FLACH 84°C an, aber real liegen 8,1% der Sommerstunden trotzdem über 95°C
(kurze Lastspitzen, die die Saisonkonstante nicht abbildet). Frühling wird von `temperature_frame`
ÜBERSCHÄTZT (99°C-Annahme impliziert IMMER >95°C, real nur 50,3% der Stunden).
Status: berechnet

---

## A4 — Wertschranke W2 neu

### Korrigierter stündlicher Spread (HKW-Ladequelle statt Biomasse, M2-Zuordnung)
**Mengengewichteter Spread (Gaskessel-MC minus HKW-Netto-MC, stündliche Stromgutschrift, nur tatsächliche
Ladestunden): 15,32 EUR/MWh** — in NUR 57,1% der Ladestunden ist der Spread überhaupt positiv (die KWK-Ladung
ist in den übrigen ~43% der Stunden TEURER als der simple Gaskessel, weil die Stromgutschrift in diesen
Stunden den hohen Brennstoffeinsatz der KWK nicht aufwiegt). Das ist DEUTLICH kleiner als sowohl der v6.1-Satz
(506,82) als auch der v7-Biomasse-Satz (70,79, jetzt verworfen).
Status: berechnet

### HAUPTBEFUND (wichtiger als der Spread-Wert selbst): Entladung in Stunden, die bei schärferer Maske gesperrt wären

| Maskenvariante | Gesperrte Stunden | S1-Entladung in diesen Stunden [MWh] | Anteil der Gesamt-Entladung (30.636 MWh) |
|---|---|---|---|
| Heizkurve `T_VL_ts` (Modell-Status-quo) | 2.033 | 969,9 | **3,2%** |
| Echte Messung (`HKW_Temp_VL.xlsx`) | 4.976 | 25.948,7 | **84,7%** |
| `temperature_frame` (Modell-Netzphysik) | 6.552 | 30.056,6 | **98,1%** |

**Das ist der wichtigste Einzelbefund dieser Runde.** Mit der Heizkurve als Maßstab (Modell-Status-quo) wirkt
die Entlademaske fast harmlos (nur 3,2% der Entladung betroffen). Mit der REALEN Messung oder dem
Netzphysik-Pfad (`temperature_frame`) — beide deutlich näher an der tatsächlichen Anlagentemperatur, s. A2 —
wären **85-98% der heutigen S1-Entladung physikalisch unzulässig.** Der gesamte bisherige TES-Wert
(165-230 k€/a) beruht auf einem Dispatch, der fast ausschließlich in Stunden entlädt, die bei korrekter
Temperaturbasis gesperrt wären. **Das ist keine kleine Kalibrierungsfrage — es stellt die Kernaussage der
bisherigen Kampagne infrage, bis E1-E3 entschieden und neu gerechnet ist.**
Status: belegt/berechnet (Eingangsreihen und Methode vollständig nachvollziehbar)

### Korrigierte Wertschranke (drei Varianten, grob, leistungsgedeckelt wie v6.1/v7)
Mit dem korrigierten Spread (15,32 EUR/MWh statt 70,79): verdrängbare Energie (Heizkurven-Maske, 14.551,6 MWh,
wie v6.1/v7) × 15,32 EUR/MWh ≈ **222.900 EUR/a** — JETZT IN DERSELBEN GRÖSSENORDNUNG wie der bestehende
TES-Wert (165-230k€/a), nicht mehr ein Vielfaches davon. Für die Messungs- und `temperature_frame`-Masken
wurde die verdrängbare-Energie-Schranke NICHT neu gerechnet (Aufwand: klein, gleiche Clustering-Methode mit der
jeweiligen Maske) — aus Zeitgründen in dieser Runde nicht mehr durchgeführt.
Status: berechnet (eine Variante) + offen (zwei weitere Varianten, Methode identisch)

---

## A3 — Temperaturpfad MM

**Bestätigt (Code):** `scripts/paper_2/scenario_runner.py` (Zeile mit
`cfg["network"]["heating_curve"]["T_supply_min_c"] = T_VL_min_effective`) injiziert NUR `T_supply_min_c`
HK-stufenabhängig — `T_supply_max_c` (bleibt 100,0, `Memmingen_P2_base.yaml:106`) und `T_outdoor_low_c`/
`T_outdoor_high_c` (bleiben −15,0/30,0, Zeile 108-109) werden NIE pro HK-Stufe verändert. `k` wird in diesem
Pfad gar nicht verwendet (v7 T1, Funktionssignatur ohne `k`-Parameter).

| HK-Stufe | `T_VL_ts` Mittel/Max/>95h | Netzpfad Mittel/Max/>95h | Differenz Mittel/Max |
|---|---|---|---|
| HK0 | 86,7 / 98,6°C / 112h | 91,9 / 97,9°C / 668h | +5,25 / +9,39°C |
| HK1 | 81,5 / 92,7°C / **0h** | 88,7 / 97,0°C / 64h | +7,11 / +10,0°C |
| HK2 | 75,8 / 85,3°C / **0h** | 87,1 / 96,6°C / 40h | +11,33 / +11,33°C |

**Kernbefund:** Der Netzpfad ist bei JEDER HK-Stufe WÄRMER als `T_VL_ts` (Differenz wächst von +5,25°C bei HK0
auf +11,33°C bei HK2) — und hat auch bei HK2 noch **40 Stunden >95°C**, obwohl `T_VL_ts` dort NULL solche
Stunden zeigt. **HK1/HK2 "funktionieren" fürs Maskensystem (reduzieren `T_VL_ts` wie gewünscht), ändern aber die
TATSÄCHLICHE Netzphysik nur über den Boden-Wert, nicht über die Steigung** — exakt wie im Auftrag vermutet.
Status: belegt (Code) + berechnet (Zahlenreihen)

---

## A5 — Netztemperaturabhängigkeit von PIN0 (offline, grobe Schätzung)

**Methode:** proportionale Skalierung der Verluste mit der mittleren ΔT zum Erdreich (`ground_temp_c=10°C`,
`Stadtbach_topo.yaml:87`) — ein einfaches `U·A·ΔT`-Verlustmodell rechtfertigt eine LINEARE Skalierung mit ΔT
als grobe Näherung (reale Verluste sind nicht perfekt linear, z.B. wegen Rohr-Isolationscharakteristik, aber
für eine Grobschätzung ausreichend).
**Status quo (`temperature_frame`, aktuell aktiv in PIN0):** mittlere `T_supply_C`=98,42°C, Jahresverlust
**19.431,0 MWh/a** (direkt aus `Q_loss_total_MW`, `output/v7_final/SB-S0-HK0-PIN0/dispatch_hourly.csv`).

| Temperaturbasis | Mittlere Temperatur | Geschätzter Jahresverlust [MWh/a] | Δ ggü. Status quo | Δ in EUR (×85,07 EUR/MWh_th, Gaskessel-Grenzkosten) |
|---|---|---|---|---|
| `temperature_frame` (Status quo) | 98,42°C | 19.431,0 | — | — |
| `T_VL_ts` (Heizkurve) | 85,57°C | **16.608,3** | **−2.822,7 MWh (−14,5%)** | **−240.100 EUR/a** |
| Echte Messung (`HKW_Temp_VL`) | 99,88°C | **19.751,6** | **+320,6 MWh (+1,7%)** | **+27.270 EUR/a** |

**Kernbefund:** PIN0 würde sich bei einem Wechsel auf die Heizkurve DEUTLICH ändern (−240k EUR/a, da die
Heizkurve im Mittel kühler ist als die aktuelle `temperature_frame`-Basis) — bei einem Wechsel auf die ECHTE
Messung dagegen NUR GERING (+27k EUR/a), weil die Messung (99,9°C) und `temperature_frame` (98,4°C) im
Jahresmittel fast identisch sind (nur die STUNDENSCHARFE Verteilung unterscheidet sich, s. A2c).
**Für E1 bedeutet das:** eine auf die Messung kalibrierte Basis würde PIN0 nur wenig verschieben (gut für
Vergleichbarkeit mit dem bisherigen PIN0-Wert) — ABER die KALIBRIERTE Heizkurve aus A2b (T_VL_min=92,35°C,
deutlich höher als die aktuelle Heizkurven-Annahme 70°C) liegt NÄHER an der Messung als an `T_VL_ts`s aktuellem
Mittel (85,57°C) — E1s "auf Messung kalibrierte Heizkurve" würde also vermutlich NÄHER am Status-quo-PIN0-Wert
liegen als die jetzige (unkalibrierte) Heizkurve.
Status: berechnet (grobe, explizit lineare Näherung — kein Solve, keine echte Netzphysik-Neurechnung)

---

## B3 — Warteschlange der AC/AE/AF-Session (nur Auflistung, nichts angehalten)

**Quelle:** `output/_ac/queue.json` + `output/_ac/scheduler.log` (read-only gelesen, nicht verändert).
Letzter Scheduler-Log-Eintrag: `2026-10-23 09:42:07` — 2 Slots belegt, 14 Jobs wartend, Bot-RAM ~69-74 GB.

| Tag | Szenario | Status | Zweck (aus `env`) |
|---|---|---|---|
| `ac1_p1_c0x1.0` | SB-S1-HK0 | **fertig** (nicht mehr in queue.json) | Neues Kostenmodell, c0×1,0 Referenzpunkt |
| `ac3_s0free_notes` | SB-S0-HK0 | **läuft** | Speicherfreie Referenz, neues Kostenmodell |
| `ac1_p3_low75k` | SB-S1-HK0 | **failed** | 75.185 EUR/MW Leistungspreis-Variante |
| `ac6_c20_k025` | SB-S1-HK0 | **läuft** | c0×2,0, 25k€/MW Leistungspreis (Basispunkt AE/AF) |
| `ac6_c20_k050` | SB-S1-HK0 | wartend | c0×2,0, 50k€/MW |
| `ac5_k010/k050/k100/k000` | SB-S1-HK0 | wartend (4×) | reiner Leistungspreis-Sweep (10/50/100/0 k€/MW) bei c0×1,0 |
| `ac6_c20_k025_ep8/ep12` | SB-S1-HK0 | wartend (2×) | E/P-Verhältnis-Sensitivität (8h/12h statt Default) |
| `ac6_c20_k025_hd2` | SB-S1-HK0 | wartend | H/D=2,0 Geometrie-Sensitivität |
| `ac6_spreiz15/20_c20_k025` + `ac4_ref_spreiz15/20` | SPREIZ-Varianten | wartend (4×) | Preisspreizung × neues Kostenmodell |
| `ac4_ref_netz50` | NETZ50 | wartend | Netzentgelt-Sensitivität × neues Kostenmodell |
| `ac3_monthly_free_old` | MONTHLY | wartend | Altmodell-Reproduktion (explizit alle 5 Env-Vars gesetzt) |

**Verwertbarkeit nach E1-E6:** JEDER dieser Läufe (außer ggf. `ac3_monthly_free_old`, der explizit das Altmodell
reproduziert) nutzt die AKTUELLE Netzphysik (`temperature_frame`) und das AKTUELLE `ΔT_TES=15K`
(`CALION_TES_C0_SCALE`/`POWER_CAPEX`/`RHD`/`P2E_HOURS` werden gesetzt, aber NIE `delta_T_scenario_k` oder die
Heizkurven-Parameter). **Wird E1 (Temperaturbasis) oder E2 (ΔT_TES) angenommen, werden ALLE diese Läufe zu
"Altmodell-Sensitivitäten"** (weiterhin gültig als Vergleichspunkte UNTER DER BISHERIGEN Temperaturannahme,
aber NICHT mehr die finale Antwort) — sie bleiben aber als E6-Kostenmodell-Sweep (Leistungspreis-Variation)
UNABHÄNGIG von E1-E3 nützlich, da E6 eine orthogonale Entscheidung ist (Kostenmodell, nicht Temperaturmodell).
Nichts wurde angehalten.
Status: belegt (Queue-Inhalt direkt gelesen) + berechnet (Verwertbarkeits-Einschätzung)

---

## B1 — Umsetzungsplan je Entscheidung (NUR Plan, nichts umgesetzt)

### E1 — Temperaturbasis (Messungs-kalibrierte Heizkurve als gemeinsame Basis)
**Betroffene Stellen:** `scripts/paper_2/scenario_runner.py:373-385` (T_VL_ts-Berechnung: `T_VL_min_c`/
`T_VL_max_c` auf die A2b-kalibrierten Werte `92,35°C`/`119,94°C` ändern, `k` bleibt stufenabhängig — NEUE
HK1/HK2-Stufen relativ dazu vorschlagen, z.B. HK1 mit kalibriertem `k≈0,8`-Analog); NEU: `T_VL_ts` als
`parameters['supply_temp_dict']` injizieren (fehlt aktuell komplett, v7 T4) — das verdrängt
`temperature_frame` automatisch (Prioritätslogik bereits vorhanden, `network_manager.py:656-718`, nichts zu
ändern). `Stadtbach_topo.yaml`s `temperature_frame`-Block kann bestehen bleiben (wird dann nie mehr erreicht)
oder entfernt werden (Aufräumen, optional).
**Änderungsumfang:** klein-mittel (2-3 Code-Stellen, keine neue Logik — die Injektion fehlt nur).
**Testfall (Build ohne Solve):** nach der Änderung muss das Build-Log `"Using temperature_frame profiles"`
NICHT mehr zeigen, sondern die explizite-Dict-Priorität (Stufe 1) greifen; `model.supply_temp_series` muss
`T_VL_ts` exakt entsprechen (Soll-Ist-Vergleich der ersten 10 Werte).
**Konsistenz-Assertion:** ein `assert` direkt nach dem Build, der `model.supply_temp_series[t] ==
T_VL_ts[t-1]` für alle `t` prüft (verhindert ein erneutes Auseinanderlaufen der beiden Pfade).
**Rückwärtskompatibilität:** `CALION_TES_RHD`-artiger Env-Override `CALION_LEGACY_TEMPERATURE_FRAME=1`, der die
Injektion überspringt und die alte `temperature_frame`-Priorität wiederherstellt — kleiner Zusatzaufwand.

### E2 — Speicher-ΔT (ΔT_TES = T_store,max − T_RL(HK) statt 15K-Boden)
**Betroffene Stelle:** `scripts/paper_2/scenario_runner.py:451` (`delta_T_scenario_k = round(T_VL_min_effective
− return_temp_c, 2)`) → `delta_T_scenario_k = round(t_store_max_c − return_temp_c, 2)` (t_store_max_c=95°C für
atmosphärisch, bereits als Konfigurationsgröße vorhanden, `t_store_max_c` in `_asset_cfg`). Hydraulik-Kappe
(`storage_geometry.yaml:252`, `power_max_mw`-Formel) mit demselben neuen ΔT statt 15K neu rechnen (reine
Zahlenänderung im Kommentar/Wert, kein Strukturwechsel).
**Änderungsumfang:** klein (eine Formelzeile + ein Konfigurationswert).
**Testfall:** `geometry.csv`s `E_TES_max_MWh` je Rung muss sich bei GLEICHEM Volumen erhöhen (D1-Tabelle als
Soll-Werte: SB-HK0 1.022 statt 438 MWh beim S1-Volumen).
**Konsistenz-Assertion:** `delta_T_scenario_k` muss im Log mit `t_store_max_c − return_temp_c` übereinstimmen,
nicht mehr mit `T_VL_min_effective`-Differenzen.
**Rückwärtskompatibilität:** bereits etabliertes Muster (`CALION_TES_*`-Envs) — ein neuer
`CALION_TES_DELTA_T_MODE=legacy_floor|store_max` Schalter.

### E3 — Entlademaske (a) gegen dieselbe Netztemperatur wie E1, oder (b) Teilentladung/Vorwärmung
**(a) Betroffene Stelle:** `scripts/paper_2/scenario_runner.py:546-555` (Maskenaufbau) — Vergleich gegen die
E1-Reihe (dieselbe `T_VL_ts`, da E1 sie bereits zur Netzphysik-treibenden Reihe macht) statt einer separaten
Reihe — **nach E1 ist dieser Punkt fast automatisch gelöst**, da Maske und Netzphysik dann dieselbe Quelle
nutzen. Änderungsumfang: **sehr klein** (kein Change nötig, wenn E1 zuerst kommt).
**(b) Teilentladung als Vorwärmung:** NEUE Modellierungslogik (kontinuierliche Entlademenge als Funktion der
Differenz `T_store − T_netz(t)` statt binärer 0/1-Maske) — bräuchte eine neue Pyomo-Variable/Constraint in
`geometric_storage.py` (Bereich um Zeile 617-624, wo die Maske aktuell multipliziert wird). Änderungsumfang:
**groß** (neue Physik, neue Tests, Validierung gegen die bisherige binäre Maske als Spezialfall).
**Testfall (b):** bei `T_netz(t) ≤ T_store,max` muss Teilentladung = volle Entladung sein (Rückwärtskompatibilitäts-Check).

### E4 — Druckbeaufschlagter Tank als Alternative
**Vorhandener Pfad geprüft:** `geometric_storage.py`s `p_max_bar`/`pressure_limits_size`-Logik (aus der
Tranche-1-A4-Analyse bekannt) unterstützt bereits DRUCKBEAUFSCHLAGTE Technologie (keine 95°C-Deckeltemperatur,
siehe `t_store_max_c=None`-Fall in `scenario_runner.py:547-548`, der die Maske dann komplett deaktiviert).
**Kostenquelle:** NICHT explizit im Repo gefunden für einen druckbeaufschlagten SB/MM-Tank bei 120°C — würde
eine neue Primärquelle brauchen (Aufwand: mittel, Literaturrecherche analog zu §4cr/AD1).
**Änderungsumfang:** klein (Konfigurationswechsel `tes_technology: pressurized`, `t_store_max_c: null`,
`p_max_bar` höher setzen), ABER die Kostenquelle fehlt noch — das ist der eigentliche Aufwandstreiber.

### E5 — Topologie j_man (bidirektional + EK an j_hkw)
**Betroffene Stellen:** `Stadtbach_topo.yaml:345-351` (`hkw_to_man`: `bidirectional: true` hinzufügen — ändert
automatisch `pipe_pair.py`s Zweig, siehe A1a); `scenarios.yaml`s `hp_assets`/`hp_nodes`-Mapping (EK aus der
`_apply_hp_location`-Verschiebung herausnehmen, nur `hp_sb` verschieben, `ek_sb` am Basis-Knoten `j_hkw`
lassen — eine Zeilenänderung in `hp_assets: stadtbach: [hp_sb, ek_sb]` → `[hp_sb]` plus eine neue, separate
EK-Konfiguration für j_hkw).
**Änderungsumfang:** klein-mittel.
**Testfall:** nach der Änderung muss `hkw_to_man_m_dot` auch NEGATIVE Werte annehmen können (Fluss Richtung
j_hkw), und `EK_SB_build`/`cap_mw` darf in einem Lauf ungleich 0 werden (aktuell IMMER 0, A3 Tranche-1).
**Konsistenz-Assertion:** Knotenbilanz an j_hkw muss EKs Beitrag jetzt enthalten.

### E6 — Neues Kostenmodell (§4cr/§4cs) als Basis
**Bereits implementiert** (bestätigt, `storage_geometry.yaml:250-256`, AD1/AD2/AD5 in
`MODEL_AND_DOE_CONTROL.md`) — **kein Code-Aufwand**, nur eine Entscheidung, ab welchem Commit/Env-Satz als
Standard zu gelten (5-Var-Rezeptur für Altmodell-Vergleich bleibt verfügbar, v7 A5d).

---

## B2 — Laufplan nach Umsetzung (nur Schätzung)

**Minimaler Kernsatz** (nach E1/E2/E3a als angenommen unterstellt; E4 nur wenn auch E4 angenommen wird):
Je Netz (SB, MM) × {PIN0, speicherfrei, frei-investierbar} × {HK0, HK2} — frei-investierbar zusätzlich ×
{atmosphärisch, druckbeaufschlagt (nur falls E4)}.

| Konfiguration | Anzahl | Laufzeit je Lauf (geschätzt, aus vorhandenen Läufen) | RAM | Slot-Bedarf (50%-Kappe) |
|---|---|---|---|---|
| PIN0 (SB) | 2 (HK0,HK2) | ~3,8h (wie bisheriges SB-PIN0) | ~10-15GB | 1 Slot |
| PIN0 (MM) | 2 (HK0,HK2) | ~9 min (wie bisheriges MM-PIN0) | <5GB | 1 Slot, kurz |
| speicherfrei (SB/MM) | 4 | ähnlich PIN0 (kein TES-Freiheitsgrad) | ähnlich | 1 Slot je |
| frei-investierbar, atmosphärisch (SB/MM × HK0/HK2) | 4 | ~8h (Matched-Effort-Standard) bis 48h bei Konvergenzproblemen (wie c0×1,3/1,5 in Tranche 1) | 40-70GB mit NodefileStart | 1 Slot je, sequenziell bei 50%-Kappe |
| frei-investierbar, druckbeaufschlagt (NUR falls E4) | 4 | unbekannt (neue Technologie, keine Referenzlaufzeit) — **Schätzung analog atmosphärisch, ~8-24h** | ähnlich | 1 Slot je |

**Gesamt (ohne E4): 12 Läufe, ~56-130h Rechenzeit** bei sequenzieller Abarbeitung auf einem Slot (50%-Kappe
lässt nur EINEN SB-Lauf gleichzeitig neben der laufenden AC/AE/AF-Session zu, siehe B3) → **ca. 3-6 Tage**
bei durchgehendem Betrieb. **Mit E4: +4 Läufe, +32-96h → insgesamt ca. 5-10 Tage.**

**Wo reicht ein Lauf mit fixierter Auslegung statt eines vollen MILP?** Die PIN0- und speicherfreien
Referenzläufe könnten (wie in v6.1 Teil C vorgeschlagen) als FIXIERTE Dispatch-Läufe laufen, wenn die
Investitionsgrößen aus einem bereits bekannten Referenzlauf übernommen werden — das würde SB-PIN0 von 3,8h auf
geschätzt 10-60 Minuten verkürzen (v6.1-Schätzung, nicht gemessen). Für die FREI-INVESTIERBAREN Läufe (das
eigentliche Ziel) ist das NICHT anwendbar — dort ist die Investitionsentscheidung selbst die Fragestellung.
Status: vermutet (Schätzungen auf Basis vorhandener Läufe, keine neuen Läufe durchgeführt)

---

## Nicht geliefert
- A2a: PPS/PSW-Rücklaufmessreihen nicht ausgewertet (nur gefunden).
- A4: Wertschranke nur für die Heizkurven-Maske neu gerechnet, nicht für Messung/`temperature_frame`-Masken
  (Methode identisch, Zeitgründe).
- A1d (MM): nur strukturelle Topologie-Vorprüfung, keine volle A1a-c-Parität.
- E4s Kostenquelle für druckbeaufschlagte Tanks: nicht gefunden (als Lücke in B1 dokumentiert, nicht behoben).

## Zusammenfassung
**Wichtigster Befund dieser Runde:** Mit der echten Messung (84,7%) oder der aktuell Netzphysik-aktiven
`temperature_frame`-Reihe (98,1%) als Maßstab wäre der GRÖSSTE TEIL der heutigen S1-Entladung physikalisch
unzulässig (A4) — die bisherige Heizkurven-Maske (nur 3,2% betroffen) hat die Kampagne bisher vor dieser Frage
abgeschirmt. A2b liefert eine konkrete, messbasierte Kalibrierung (`T_VL_min=92,35°C`) als direkte Grundlage
für E1. A1 zeigt, dass j_mans Sackgassen-Topologie eine fundamentalere Erklärung für S2/S3s `build=0` ist als
die (ohnehin zu hohe) Leistungskappe aus B4. B1/B2 liefern konkrete Umsetzungspfade (meist klein-mittel
Aufwand, E6 bereits erledigt) und eine Laufzeitschätzung (~3-10 Tage für den Kernsatz).

**STOPP — wartet auf Lukas' Entscheidungen E1-E6.**
