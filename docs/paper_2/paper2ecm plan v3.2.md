# Paper 2 — Plan v3.2 (Stand 2026-09-14)

**Ersetzt `PAPER2_ECM_PLAN_v3.md` vollständig.** v3 enthält an mehreren Stellen
Anweisungen, die inzwischen widerlegt sind (Cap-Anhebung, degressive Kostenkurve als
Alternative zum Multi-Tank, C2 als Volumen-Zielkonflikt). Wer v3 liest, ohne dieses
Dokument zu kennen, baut Falsches. Ebenso sind Teile von `AGENT_PROMPT_Paper2_v3.md`
überholt — die Korrekturen stehen in §7.

Zieljournal: *Energy Conversion and Management* (≈9.000 Wörter, ≤15 Elemente Haupttext).

---

## 1. Was seit v3 festgezurrt ist — Modell

| Thema | Entscheidung | Begründung / Quelle |
|---|---|---|
| **Speichertechnologie** | Atmosphärischer Stahltank als **einzige** Basis, beide Netze, alle 62 Läufe. Druckbeaufschlagt nur als Study-G-Sensitivität. Erdbecken entfällt. | Technologie ist eine Folge der Größe, kein frei kreuzbarer Faktor |
| **Kostenfunktion** | `C = N · c₀ · ((V/N)/v₀)^b`, c₀ = 2,5 M€ @ v₀ = 10.000 m³ (= 250 €/m³), **b = 0,70**, **β = 0** (turnkey), unit = 10.000 m³, **v_min = 50 m³** | Anker: IEA-DHC Annex XII (TTES 100–400 €/m³, größendegressiv). b aus Materialskalierung, nicht aus einem 2-Punkt-Fit |
| **Pro-Tank-Auswertung** | Kurve wird **nie** auf das Gesamtvolumen angewandt | Fünf Tanks à 9.200 m³ liefern nicht die Skaleneffekte von 46.000 m³ (Δ ≈ 43 %) |
| **Temperaturdecke** | ~95 °C, **aktiv**, inkl. Entlademaske `T_Speicher ≥ T_VL(t)`. `HOT = min(T_VL,max, 95 °C)` | Physik der Technologie, nicht opt-in |
| **Auslegungs-ΔT** | **15 K**, aus der VDI-6002-Mindestspreizung an den Übergabestationen | Die Schranke ist in ~⅓ der Heizstunden aktiv (SB 2.901 h, MM 3.192 h/a). **Nicht** „die Heizkurve bestätigt 15 K" — der Floor wird erzwungen |
| **Stillstandsverlust** | `U · k(AR) · V^(2/3) · ΔT`, identische Formel in Dispatch- und Investitionsklasse | Sonst vergleicht die Sweep-vs-MILP-Kreuzvalidierung zwei Modelle |
| **Rücklaufverlust** | In der Bilanz **bepreist** | Validiert: +28 k€ / +11,8 % auf die LP-Zielfunktion. Vorher kostenlos → systematische Unterkostung |
| **min_load** | **Bleibt.** Keine Relaxierung | Die Biomasse fiele in 59 % der Sommerstunden unter ihre Mindestlast; der Überschuss muss gespeichert werden. Das ist der Mechanismus, der dem Speicher Wert gibt |
| **j13_to_j15** | Basis U = 0,28/0,30; Original 1,31/1,40 als dokumentierte Sensitivität | Vor- und Rücklauf um denselben Faktor 4,67 verschoben → Datenartefakt, kein Bauzustand |
| **Nachfragedefinition** | **Geliefert** (LCOH-Nenner) vs. **erzeugt** (Brennstoff/CO₂) — getrennt ausgewiesen | 30 % Unterschied; Verwechslung verschiebt jede LCOH-Zahl |
| **Emissionsfaktor** | Stündlicher Netz-EF als Basis. **Keine Granularitätsanalyse** | Das ist Paper 3s Thema — nicht kannibalisieren. Ein Satz plus Vorwärtsverweis |

---

## 2. Was festgezurrt ist — Methode

**Es gibt keine bewiesene Optimalität.** Der LP-Bound liegt bei ~265–288 k für *jedes*
Szenario, auch für solche ohne Speicher — die Relaxierung unterscheidet nicht einmal
„kein Speicher" von „Speicher am Zentralknoten". Besseres Lösen schließt diesen Bound
nicht. Die Berichterstattung steht deshalb auf drei Säulen:

1. **Matched-effort-Protokoll.** Jedes Szenario: dieselbe Seed-Konstruktion, dieselben
   Solver-Einstellungen, dasselbe Zeitbudget (2 h). Berichtet wird der beste Inkumbent
   plus sein Gap. Unterschiede sind dem Szenario zurechenbar, nicht dem Solverglück.
2. **Dominanz-Gate.** Kein Szenario darf schlechter berichten als ein Szenario, dessen
   zulässige Menge es enthält (S0 ⊂ jedes TES-Szenario über Sprosse 0). Gestaffelt:
   **> 1 % → `failed`** (nicht berichtet), **0–1 % → `suspect`** (berichtet, markiert,
   nicht gegen seinen Erben gerankt). Schwelle provisorisch bis zur Stabilitätsprüfung.
3. **Inkumbenten-Stabilität.** 2–3 Szenarien mit 12-fachem Budget. Die dort gemessene
   Drift ist die **Interpretationsschwelle** — nicht der MIP-Gap. Darunter wird nicht
   interpretiert.

**Kampagnenmechanik für TES-Szenarien:** geseedete TES-**fixierte** Leiter-Sweeps.
Sprosse 0 ist auf S0 verankert → Dominanz per Konstruktion. Die vollen Sweeps liefern
zugleich die F2-Kurve. Vererbung in das TES-investierbare Modell scheitert an
`FeasibilityTol` → Future Work.

**Solver-Integrität.** Die eingefrorene Juli-Kampagne lief mit `MIPFocus=1`/ohne Cuts,
nicht mit den dokumentierten `Cuts=2`/`MIPFocus=2` (Clobber seit 2026-05-20, belegt aus
einem unberührten Log). Behoben; `verify_solver_params.py` liest die tatsächlichen
Gurobi-Parameter zurück, schreibt sie ins Manifest und bricht bei Abweichung laut ab.
Berichtet wird, was tatsächlich lief.

**Auswertungsregel.** *Die Auswertungsschicht rechnet keine physikalische Größe nach —
sie liest, was das Modell geschrieben hat.* Zwei Bugs derselben Klasse sind bereits
aufgetreten (hartkodiertes ΔT in `f2_capex.py`, umgangener v_min-Filter). Alle übrigen
Generatoren (CAPEX, LCOH, CO₂, Speicherstunden, Netzverlust, `geometry.csv`/`r_hd`)
sind darauf durchzusehen.

---

## 3. Versuchsplan (62 Läufe)

Gegenüber v3 um 16 Läufe erweitert; jede Ergänzung belegt eine Aussage, die im Paper steht:

| Ergänzung | Läufe | Belegt |
|---|---|---|
| `TES-ONLY` (TES investierbar, neue HP/EK = 0, Bestand unverändert) | +6 | „Einsparung aus Speicher + Heizkurve, nicht aus der WP" |
| `FREE-CO` (endogen, co-located, **normal** beladen) | +6 | Kette FREE → FREE-CO → FREE-CO-HOT, ein Faktor je Schritt |
| `BASE-HK0` (Baseline bei realer Heizkurve) | +2 | Δ bündelt nicht mehr Investition **und** HK-Einführung |
| `FIX-HP-TVLFIX` | +2 | Wert der Heizkurvenregelung **mit** Speicher |

Interne IDs bleiben stabil; das Paper nutzt semantische Labels aus **einer**
Mapping-Tabelle (`scenario_labels.py`). Study G steht als eigene Klasse in T2, nicht in
der Investitionsmatrix.

**Reihenfolge:** Study C (Siting-Enumeration, feste Standorte, leichte Klasse, F4-Basis)
**zuerst**. Endogene MILPs zuletzt bzw. ins Supplement mit ausgewiesenen Gaps — sie
konvergieren nicht verlässlich und tragen keine Kernaussage.

---

## 4. Abbildungen

F1 Netze · **F2 Speicherauslegung** (Kern; b-Band sichtbar, „nicht baubar"-Schattierung
über der Oberkante) · F3 COP und Netto-TAC über HK · **F4 Siting-Landschaft** (Verteilung
statt Max/Min-Ratio, Artefakt-Check auf Knoten an Druck-/Kapazitätsgrenzen) · F5
aggregiert vs. nodal · F6 Break-even-Karte · F7 Tornado.

**C2 ist umgerahmt.** Nicht mehr „Heizkurve koppelt an Speichergröße", sondern:

> In Bestandsnetzen setzt nicht die Heizkurve, sondern die **Mindestspreizung an den
> Übergabestationen** die nutzbare Energiedichte des Speichers — und damit dessen
> Kosten pro MWh.

Beide Netze liegen bei Normalbeladung an derselben 15-K-Schranke, deshalb hilft und
schadet die HK-Absenkung dem Speicher nicht. Nur Heißbeladung koppelt (MM 31,4 K vs.
SB 35 K, ~12 %). **Ein Absatz plus Tabelle, keine eigene F3-Spalte.**

Planungshinweis für die Diskussion: Ein Substationsertüchtigungsprogramm, das die
15-K-Schranke senkt, verbilligt den Speicher direkt.

---

## 5. Zurückgezogene Aussagen

Diese Zahlen dürfen **nicht** weiterverwendet werden:

- **+44,8 % Memmingen** — Baseline nicht sauber definiert; Modell hat sich geändert
- **77× schlechtestes Siting** — Verdacht auf ungleiche Konvergenz statt Standorteffekt
- **„endogen schlägt fest"** (MM −13,2 %, SB −3,2 %) — innerhalb der Gaps
- **HK-Effekt −4,4 %** — innerhalb der Gaps
- **„Juli MM-S1 löste auf 1,4 %"** — falsch; das war die F3-Enumeration. MM-S1-HK0 stand
  auf `maxTimeLimit`
- **500 MWh Bestandsspeicher Stadtbach** — Phantom, 2026-07-08 entfernt. Realer
  SB-Bestand: 9,9 MW P2H
- **344 k als MM-S1-Referenz** — aus dem Modell ohne bepreisten Rücklaufverlust
- **F2-Optima 0,5 / 1,1 MWh** — unter v_min (16,6 bzw. 36,5 m³)
- **13/38 Läufe der eingefrorenen Kampagne** standen auf `maxTimeLimit` mit nicht
  erfassten Gaps. Jede Abbildung, die einen davon enthält, ist potenziell grob falsch

---

## 6. Offene Punkte, in Reihenfolge

1. **Study C** — Siting-Enumeration. Größter Posten, F4-Basis, noch nicht begonnen.
2. **Monotonie-Check über 2,2 MWh** (null Rechenzeit). Steigt die Kurve ab der kleinsten
   gültigen Sprosse, liegt das Optimum unter v_min → Befund „optimaler Speicher kleiner
   als der kleinste baubare Behälter", und die feine Leiter entfällt.
3. **S0-Anker enger lösen.** Eine Ersparnis von 4,5 % gegen einen Anker mit 4,5 % Gap ist
   keine Aussage. Gatet **alle** Prozentzahlen des Papers.
4. **Auswertungsschicht durchsehen** nach der Regel in §2.
5. **S2 (MM)**: forced-build-Unzulässigkeit per IIS als **Ergebnis** benennen, nicht
   ausschließen — Faktorsymmetrie.
6. **Stabilitätsprüfung** (2–3 Szenarien, 12× Budget) → Interpretationsschwelle.
7. **SB-Neutralitätsprüfung** vor der SB-Produktion.
8. Endogene MILPs, Supplement.
9. Abbildungen und Tabellen aus den korrigierten Daten neu bauen.
10. **Zenodo-Deposit** — ECM Data Statement Option C verlangt DOI. Pflicht, nicht optional.

---

## 7. Korrekturen an `AGENT_PROMPT_Paper2_v3.md`

Der Agenten-Auftrag v3 ist an vier Stellen überholt:

1. **„V_TES_max von 5.000 auf 50.000 m³ anheben"** — falsch. Die 5.000 m³ sind eine
   begründete ASME/PED-Dünnwandherleitung für *einen* Behälter. Richtig ist die
   Multi-Tank-Leiter mit `unit_tank_m3`, nicht die Anhebung der Behältergrenze.
2. **„Degressive Kostenkurve `c₀·(V/V₀)^b`"** — gilt, aber **pro Tank**, nicht auf das
   Gesamtvolumen, und mit β = 0.
3. **ΔT(HK)-Kopplung „fehlt und muss gebaut werden"** — sie existiert seit 2026-07-08
   und ist korrekt. Der Befund ist, dass sie wegen des 15-K-Floors über die HK-Stufen
   **invariant** ist.
4. **Mindestteillast relaxieren** — geprüft und verworfen (siehe §1).

Gültig bleiben: Gap-Disziplin, STOP-Punkte, Reproduzierbarkeitspaket, „kein
stillschweigender Parameterwechsel", Provenienz im Manifest.

---

## 8. Zwei Regeln, die weiter gelten

1. **Faktor-Regel.** Ein neuer Faktor kommt nur in den Versuchsplan, wenn er eine
   Aussage verändert, die im Paper tatsächlich steht.
2. **Freeze.** Was auffällt und die Gültigkeit eines berichteten Ergebnisses nicht in
   Frage stellt, geht auf die Future-Work-Liste — nicht in die Kampagne.

Der Freeze schützt Features, nicht Korrektheit: Ein Fix, der ein berichtetes Ergebnis
ungültig machen würde, ist vom Freeze ausgenommen.

---

## 9. Zeitplan

Kernphysik und Methodik sind gelöst; was bleibt, ist Rechenzeit und Konsolidierung.
Realistisch **rund eine Woche bis zum vollständigen, geprüften Ergebnissatz** (Study C
ist der lange Pol), danach zwei bis drei Wochen Manuskript.

Das größte Risiko ist nicht Rechenzeit, sondern das Muster, dass jeder Fix den nächsten
Fund freilegt. Regel 2 ist die Gegenmaßnahme.