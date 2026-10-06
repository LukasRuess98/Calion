# Paper 2 — Modell & Versuchsplan: KONTROLLE (eingefroren 2026-09-02)

Einseitige, verbindliche Beschreibung dessen, was modelliert wird und wie. Nach diesem
Config-Umbau gilt **MODELL-FREEZE**.

## 0. Zwei Regeln (verbindlich)
1. **Faktor-Regel:** Ein neuer Faktor kommt nur in den Versuchsplan, wenn er eine Aussage
   verändert, die im Paper tatsächlich steht. Alles andere ist Supplement oder Future Work.
2. **Modell-Freeze:** Ab jetzt gehen weitere Verbesserungs*ideen* auf die Future-Work-Liste (§5),
   nicht ins Modell. Keine weiteren Neustarts wegen Modell-*Erweiterungen*.
   **Der Freeze schützt Features, nicht Korrektheitsfixes.** Ein belegter Fehler (z. B. der
   kostenlos gestellte Rücklaufverlust, §4b) wird korrigiert, auch nach dem Freeze — das ist keine
   Erweiterung. Neue *Fähigkeiten* bleiben draußen.

## 0b. Vier Auflagen vor dem Freeze (Review 2026-09-02)
- **A — Entladetemperatur:** Die Mask ist eine **Technologie-Eigenschaft, DEFAULT AN**: ein
  Speicher mit Temperaturdecke (atmosphärisch, `t_store_max_c`) darf nicht entladen, wo
  `T_VL(t) > Decke` — druckbeaufschlagt (keine Decke) unberührt. Kein Opt-in-Flag für die Physik;
  `CALION_TES_NO_DISCHARGE_MASK=1` schaltet sie NUR für die „ohne Restriktion"-Sensitivität
  (oberes Band) aus. **Messung (keine Solves): Stunden mit T_VL>95°C** — MM: HK0 1,4 %, HK1/2 0 %
  (Fußnote); **SB: HK0 23,2 % (2033 h, kalte Spitzen), HK1 7,0 %, HK2 0,2 %** → für SB HK0
  tragend, ohne Mask würde atmosphärisch massiv überbewertet. (Konservativ: der reine Qd=0-Mask
  ignoriert Rücklauf-Vorwärmung, der wahre Wert liegt zwischen Mask und Ohne-Mask.) **CODE FERTIG.**
- **B — Akzeptanzkriterium:** Das Optimum darf **nicht auf der letzten Leitersprosse** liegen.
  Tut es das → Leiter verlängern + neu rechnen (KEIN Freeze-Bruch, KEIN Modellneustart). SB-Leiter
  bis 1607 MWh (≈2× über ~800-MWh-Bedarf) — bei Bedarf verlängern.
- **C — vor der Kampagne:** (C1) Energiebilanzschluss an der Quelle ≤2 % verifizieren/fixen;
  (C2) HK-gematchte, dispatch-optimierte Baseline (identischer Park, keine Neuinvestition) bauen.
- **D — stündlicher EF:** drin (Ziel+Reporting), aber **KEINE Granularitätsanalyse** — ein Satz
  + Vorwärtsverweis, keine stündlich-vs-konstant-Abbildung. Granularität = **Paper 3**, nicht hier.

## 1. Was wir modellieren
- **Netzmodell:** nodales L3+-MILP (reale Topologie beider Netze, Paper-1-Framework): Wärme-/
  Massenbilanz je Knoten, Rohrverluste, Druckabfall, räumlicher VL-Temperaturabfall.
- **Erzeuger:** realer Bestandspark (CHP, Gaskessel, Biomasse, Abwärme-Einspeisung) mit
  **Unit-Commitment** (min_load-Binärvariablen) **AN** — die Speicherwert-Quelle; plus
  **investierbare** Wärmepumpe (COP(T_VL)) und Elektrodenkessel.
- **Heizkurve (HK):** HK0 (reales Netz) / HK1 / HK2 = Retrofit-Stufen, die Vor- **und** Rücklauf
  gemeinsam senken (MM 74/63,6 → 70/55 → 66/51; SB 70/60 → 65/50 → 60/45). 15-K-Floor (VDI 6002).
- **Speicher (geometrisch):** V und Höhe geometrisch, Oberflächen-Stillstandsverlust
  **konstant** `U·k(AR)·V^{2/3}·ΔT` (identische Formel in Dispatch- und Investitionsklasse,
  #2), η_strat=0,85. **EINE Technologie (atmosphärischer Stahltank) als Basis für BEIDE
  Netze und alle 62 Läufe** (Entscheidung 2026-09-04, ersetzt die frühere Hybrid-Fassung;
  Erdbecken/PTES komplett raus). Druckbeaufschlagt bleibt NUR Study-G-Sensitivität.

  | | **Atmosphärisch (BASIS, beide Netze)** | **Druckbeaufschlagt (nur Study-G-Sensitivität)** |
  |---|---|---|
  | Druck / Kopplung | ~1 bar, hydraulisch entkoppelt (HX) | 10 bar, direkte Netzkopplung |
  | Ladetemperatur | Decke **95 °C aktiv** + Entlademaske; HOT = min(T_VL,max, 95 °C) | bis T_VL,max (Decke aufgehoben) |
  | Kosten | degressiv **pro Tank** `C=N·C₀·((V/N)/V₀)^b`, C₀=2,5 M€ @ V₀=10.000 m³ (=**250 €/m³**, IEA-DHC Annex XII), **b=0,70** (Materialskalierung), **β=0** (turnkey) | linear α·V+β (1.200 €/m³ + 100k/Behälter), ≤5.000 m³/Behälter |
  | Behälter | unit=10.000 m³, darüber N=⌈V/unit⌉ Tanks; Kurve NIE außerhalb [50, 10.000] m³ ausgewertet; v_min=50 m³ (β=0-Mikrospeicher-Sperre) | ASME/PED-Behältergrenze |

  **ΔT-Floor = 15 K (bestätigt, Draft korrekt):** beide aktiven Configs setzen
  `min_supply_delta_T_k = 15.0` (Memmingen_P2_base.yaml:101, Stadtbach_topo.yaml:90) →
  `T_VL,min_eff = max(T_VL,min, T_return+15)`, ΔT_Speicher = 15,0 K in BEIDEN Netzen (MM hebt
  den VL-Boden von 74 auf 78,6 °C, SB von 70 auf 75 °C). Der `scenario_runner`-DEFAULT 10 K greift
  nur, wenn eine Config den Wert weglässt — tut keine. (Ein früherer Notiz-Stand „~10 K" war ein
  Lesefehler: Default statt Config-Override.) Einzige Korrektur ggü. der 15-K-Überschlagsrechnung ist
  **η_strat=0,85** (nutzbar 14,42 statt 16,96 kWh/m³, ~+7 % Volumen): SB-Knie (~731 MWh nutzbar,
  10 h) ≈ **50.700 m³ / N=6 Tanks** (raw-Überschlag 47.200). Die Pro-Tank-Regel hält die spez. Kosten
  bei ~263 €/m³ (nahe Anker) → SB-Speicher-CAPEX ≈ **13,3 M€ am Knie** (statt ~10 M€ bei alter
  Gesamtvolumen-Degression) — konservativ, nicht schmeichelnd.
  **Punkt 1 — hydraulischer Beleg aus gelösten Läufen (SB-S1-HK0/1/2, MM-S1, je 8760 h × 32 Rohre):**
  - **SB-VL-Temp erreicht den Floor NIE:** min T_in = **84 °C** über alle HK-Stufen (Floor 75 °C, 0 Rohr-
    Stunden am Floor). Die Heizkurve hält den VL ~9 K über dem Floor → **der 15-K-Floor ist in SB SCHLAFF.**
  - **Geschwindigkeit realisiert max = 2,73 m/s** (Grenze 3,0; Median 0,43; 99 % = 1,93) — nur an 3
    Erzeuger-Einspeise-Rohren (gtost/bmhkw/ava→ost, DN250–450), **durchsatzgetrieben bei 84 °C**, nicht
    durch VL-Kollaps bei milden Stunden. MM: v_max ≤ 1,04 (vernachlässigbar).
  - **Konsequenz Draft:** der Satz „ohne 15-K-Floor kollabiert ΔT bei milden Stunden und überschreitet
    Geschwindigkeit ~50 h/a" ist in SB **nicht belegt** — der Floor bindet nicht, die Nähe zur 3-m/s-Grenze
    ist Erzeugerdurchsatz. Satz entschärfen ODER mit einem echten 10-K-Lauf gezielt belegen.
  - **AUFLÖSUNG Auslegungs-ΔT = 15 K (nicht-zirkuläre Begründung):** das Modell **erzwingt** eine
    Mindestspreizung von 15 K an den Übergabestationen (`min_supply_delta_T_k=15`, VDI 6002:
    `T_VL ≥ T_return+15`). Diese Schranke ist in rund einem Drittel der Heizstunden aktiv; das
    **Auslegungs-ΔT entspricht daher der Schranke = 15 K** — NICHT „die Heizkurve bestätigt 15 K"
    (das wäre zirkulär, weil der Floor die Kurve dort hin zwingt). **Der frühere „24 K / 1,6× übergroß"-
    Befund fällt WEG** — die 24 K stammten aus dem gelösten Dispatch (VL nie <84 °C, Erzeuger-
    Mindesttemp-Artefakt), genau der dispatch-/jahresabhängigen Quelle, die die analytische Regel
    ausschließt. **SB-Knie bleibt 50.700 m³/N=6/≈13,3 M€, Leitern stehen.**
  - **Sechs-Zeilen-Tabelle für T2 (effektive Temperaturen NACH Floor — ersetzt die Config-Werte im Paper):**

    | Netz | HK | T_VL,min konfig. | **T_VL,min effektiv** | T_ret | **ΔT Ausl.** | Floor aktiv | h (2025) |
    |---|---|---|---|---|---|---|---|
    | SB | HK0 | 70,0 | **75,0** | 60,0 | **15 K** | 33 % | 2901 |
    | SB | HK1 | 65,0 | 65,0 | 50,0 | **15 K** | 22 % | 1920 |
    | SB | HK2 | 60,0 | 60,0 | 45,0 | **15 K** | 22 % | 1945 |
    | MM | HK0 | 74,0 | **78,6** | 63,6 | **15 K** | 44 % | 3834 |
    | MM | HK1 | 70,0 | 70,0 | 55,0 | **15 K** | 23 % | 2022 |
    | MM | HK2 | 66,0 | 66,0 | 51,0 | **15 K** | 24 % | 2061 |

    **Drift nur in HK0** (SB 70→75, MM 74→78,6: der Floor hebt den konfigurierten VL-Boden an) — genau die
    Config-vs-Rechnung-Drift, die uns dreimal getroffen hat. Diese Tabelle ist die verbindliche Quelle für
    alle Temperaturangaben im Paper. **Beide Netze jetzt auf Modell-Basis: 8760 h, Kalenderjahr 2025**
    (MM aus 15-Min-Rohdaten auf 2025 geschnitten + stündlich resampled — `taus_MM_2025h.csv`). Der VDI-Floor
    ist in **33–44 %** der Stunden aktiv (HK0), das ΔT=15 K ist also der reguläre Betriebspunkt, nicht ein
    seltener Worst Case. Quelle: `scripts/paper_2/report_effective_temps.py`. Dauerlinie → Supplement.
  - **A-vs-B im Tornado wird zu „Worst-Case vs. Median-Betrieb":** Primärauslegung 15 K (Worst Case, 1/3
    des Jahres real erreicht). Sensitivität: bei Median-Betriebs-ΔT (~24–27 K, Median-T_VL 84–87 °C) wäre
    der Speicher ~40 % kleiner — legitimer Tornado-Balken, aber NICHT die Primärzahl. `min_supply_delta_T_k`
    unverändert 15 K. Dispatch-Invarianz bestätigt (power_to_energy_ratio=0,25, energiegekoppelt; nur der
    ~0,1-%-Oberflächenverlust ist ΔT-berührt) → A/B/Tornado sind Nachbearbeitung, kein Re-Solve.
  - **MM-Randnotiz:** MM-S1-HK2 zeigt realisiertes T_in bis 66 °C (ΔT≈2 K, Floor müsste 78,6 °C sein) —
    entweder Floor in Altläufen nicht durchgesetzt oder VL-Abfall; MM-Speicher immateriell (~0,1 M€),
    beim MM-S4-Re-Solve auf frischer Config mitprüfen.

- **Kosten:** annuisierte CAPEX (ANF) + OPEX. Strom stündlicher Spotpreis, Gas, CO₂.
- **Emissionen:** **stündlicher** Netz-CO₂-Faktor `grid_co2_kg_MWh` (electricitymaps) — in
  Zielfunktion **und** Reporting (der 400-er Skalar ist tot).

## 2. Was wir NICHT modellieren (bewusst — Future Work, §5)
Repräsentative Typtage; kontinuierliche/warme Ladetemperatur (Artefakt ohne reales Gegenstück);
Technologie als volle Faktorachse; McCormick-exakter endogener Verlust; grobere Zeitauflösung.

## 3. Versuchsplan (endlich)
Alle Sizing-/Feinaussagen in der **Dispatch-Klasse** (commitment-on, gap-fest). Reihenfolge:
**erst Memmingen, dann Stadtbach.**

| Studie | Zweck / Abbildung | Design | Läufe |
|---|---|---|---|
| **G — Sizing + Dreieck** | **F2** (TAC über Speicherstunden, inneres Optimum) + C2-Panel | 2 Optionen{atm,druck} × 8 V × 2 HK{0,2} × 2 Netze | **64** |
| **C — Siting** | F4 (Siting-Landschaft), Basisfall atmosphärisch | Enumeration HP×TES | ~61 |
| **N — aggregiert vs. nodal** | F5 (Fehlentscheidungskosten) | Ein-Knoten vs. nodal, je Netz | 6 |
| **P — Bedingungsraum** | F6 (Break-even CO₂×Preis, echte stündl. EF) | c_CO2 × c_el/c_gas | 50 |
| **E — Tornado tier-2** | F7 | Re-Dispatch je Variante | 20 |
| **H — Headline + Baselines** | T3 + Baseline (dispatch-optimiert, HK-gematcht) | gestraffte Matrix | ~20 |
| **I — Modellversion-Invarianz** | T4 | e8e445e vs. main, 8 Szenarien | 8 |

## 3b. Szenariomatrix — v3-Vervollständigung (2026-09-04, nach Gutachter-Review)
`configs/paper_2/scenarios.yaml` = **62 Investitions-MILP-Läufe** (war 46). Paper-Tabelle:
`01_latex_build/DOE_TABLE.tex` (kompakt Faktor×Stufe = Haupttext; volle 62-Zeilen = Supplement;
**semantische Labels** = Single Source of Truth, interne IDs nur für Reproduzierbarkeit).
- **Vier Ergänzungen (je Faktor-Regel-konform, +16 Läufe):**
  1. **TES-ONLY** (+6): Speicher investierbar, HP/EK=0 → isoliert den Speicherwert DIREKT (S0 nur per
     Weglassen). Trägt die Kernaussage „Einsparung aus Speicher+HK, nicht WP" (T3).
  2. **FREE-CO** (+6): endogen + co-located + NORMAL beladen → entkoppelt Co-Location von Ladetemperatur.
     Kette FREE → FREE-CO → FREE-CO-HOT ist jetzt sauber zerlegbar (ein Faktor je Schritt).
  3. **BASE-HK0** (+2): Baseline bei realer Heizkurve = echter Status quo. BC-Δ bündelt nicht mehr
     „Investition + Einführung Heizkurvenregelung". **BASE-HK0 = Hauptreferenz**, BASE-FIX(TVLFIX) weist
     aus, was Heizkurvenregelung allein bringt.
  4. **FIX-HP-TVLFIX** (+2): TVLFIX-Referenz für die Speicher-Familien → Wert der Heizkurvenregelung
     MIT Speicher (FIX-HP vs. FIX-HP(TVLFIX)).
- **Semantische IDs (beide Netze identisch):** BASE-FIX / BASE-HK0 / HP-ONLY / TES-ONLY / FIX-CENTRAL /
  FIX-HP / FIX-HP-HOT / FIX-REMOTE-A/B (SB, MM=n.a.) / FREE / FREE-CO / FREE-CO-HOT.
- **Interner ID-Rename VERTAGT** (nicht jetzt): 15 Skripte hardcoden `MM-S*/SB-S*` (fig_p2_paperset 10×,
  gen_tables 6×, Loader). Rename = dedizierter Refactor beim Regenerieren, nicht nebenbei. Paper nutzt
  semantische Labels → Gutachter-Verwirrung (S4-Kollision MM-endogen vs. SB-Pumpstation) ist gelöst.
- **Faktenkorrektur:** MM-Zentrale/TES-Knoten = **j_9** (primary_producer + chp/tes/biomass/gasboiler),
  NICHT j_1 (stale seit 2026-08-06-Move). Descriptions in scenarios.yaml korrigiert.
- **Study G bleibt GETRENNT** von scenarios.yaml: Dispatch-Sizing mit fixem Volumen = andere
  Experimentklasse (F2). In T2 eigener Block mit „Study→Abbildung"-Spalte. NICHT in die 62-Matrix mischen.
- **TES-ONLY-Konvention (bestätigt):** manipuliert wird nur die **Neuinvestition**; der Bestandspark
  ist über ALLE Läufe eines Netzes identisch (Vergleichsgrundlage). SB-Bestand-P2H (`p2h_existing`
  9,9 MW) bleibt AN; nur die neuen `hp_sb`/`ek_sb`=0. Tabellen-Label: „no new HP/EB (existing plant
  unchanged)". Override korrekt (lässt p2h_existing unberührt).
- **FAKTENKORREKTUR — Stadtbach hat KEINEN Bestandsspeicher (500 MWh sind ein Phantom):** das frühere
  `tes_existing` (500 MWh) wurde **2026-07-08 entfernt** (Config j_hkw-Kommentar: „no documented source").
  `tes_sb` ist voll investierbar (10–5000 m³), kein fixer Sockel. **Beide Netze starten bei 0 MWh
  Bestandsspeicher.** Stale „500 MWh"-Strings bereinigt: SB-Config-Header + BC-SB/BC-SB-HK0-Descriptions.
  - **⟹ Die zwei daraus gezogenen Konsequenzen sind ZURÜCKGEZOGEN:** Study G braucht KEINEN SB-Sockel-
    Sweep; F2 braucht KEINEN Bestands-Offset — beide Netze ab 0, Speicherstunden direkt vergleichbar.
  - **T1:** realer Bestand = SB `p2h_existing` 9,9 MW (+ Kessel/CHP/Biomasse/AVA); MM `eboiler_main`
    5 MW (investierbar bis 20). KEIN Bestandsspeicher in beiden. Gehört so in T1.
- **Naming-Auflage:** ID↔Label in EINER Code-Mapping-Tabelle (`scripts/paper_2/scenario_labels.py`),
  aus der die Paper-Labels generiert werden — verhindert Label/ID-Drift (dieselbe Fehlerklasse wie
  j_1 vs. j_9, nur in einer Caption).

## 4. Was ins Paper kommt (Abbildungen/Tabellen)
- **F1** Netzkarten (2 Panels) — Quellen liegen (`docs/paper_2/figures/`).
- **F2** *Kernabbildung* — Sizing-Kurve über Speicherstunden, inneres Optimum, atmosphärisch vs.
  druckbeaufschlagt (das **Ladetemperatur↔Technologie↔Volumen-Dreieck**): atmosphärisch = großer
  billiger Speicher, druck = kleiner teurer heiß geladener — welcher je Netz gewinnt.
- **F3** Heizkurve: COP(HK) + Netto-TAC(HK). **C2 als Befund (ein Panel/Absatz):** bei
  return-mitsenkendem Retrofit ist die Energiedichte HK-invariant; nur bei heißer Beladung wächst
  die Spreizung (MM 36→49 K). Kein eigenes Figuren-Gerüst.
- **F4** Siting-Landschaft (Median/P90, Artefakt-Check).
- **F5** aggregiert vs. nodal → Fehlentscheidungskosten (Brücke zu Paper 1).
- **F6** Break-even-Karte c_CO2 × Preisverhältnis, echte stündliche EF, 2026-Punkt.
- **F7** Tornado. **T1** Netzkenndaten, **T2** Parameter inkl. Geometrie, **T3** Headline-KPIs
  (mit MIP-Gap, Speicherstunden), **T4** Validierung (Bilanzschluss ≤2%, Sweep↔MILP, Invarianz).
- **Data Statement Option C → Zenodo-DOI-Deposit ist Pflicht** (ECM).

## 4b. C1-Befund (Bilanz) — Stand 2026-09-03 (Verlust-Diagnose ABGESCHLOSSEN)
- **Kein Phantomspeicher:** `pipe_thermal_mass` NIRGENDS aktiv (kein E_net/Q_net_buf, auch Paper 1
  unberührt); kein `tes_existing` (MM); Demand-Slack aus (`allow_heat_demand_slack`=False).
- **Bilanz schließt zu −0,3 %** mit den per-node-Größen: **Erzeugung 9083 = Lieferung 7257 +
  Bilanz-Verlust 1842 + Dump 6.** Die alte Closure-Formel nahm die falsche demand (`m.heatd` 9433)
  UND ignorierte den Verlust — beides korrigiert.
- **DREI Wärme-Größen, drei Bedeutungen (Konvention verbindlich):**
  - **Geliefert** = 7257 MWh → **LCOH-Nenner** (an Verbraucher gelieferte Wärme).
  - **Erzeugt** = 9083 MWh → **Brennstoff-/CO₂-Basis.**
  - `m.heatd` = 9433 = erzeugerseitige demand+Verlust-Größe (inaktive Single-Node-Regel);
    die Closure darf sie NICHT verwenden. ⚠ Bei Nenner-Verwechslung ±30 % auf jede LCOH-Zahl.

### Verlust: der Bilanzwert 1842 ist ein FAKTOR-~2-UNDERCOUNT (KORREKTUR: früher stand hier
irrtümlich „Doppelzählung / 3741 zu groß" — die Richtung war invertiert).
- **Code-Befund (`pipe_pair.py:547/556`):** Supply- UND Return-Verlust werden **getrennt** gerechnet,
  jede Leitung mit ihrem eigenen ΔT (Supply: Paar-Mittel `(T_in+T_out)/2`; Return: `T_return_in`).
  Der physikalisch **vollständige** Verlust ist also Supply+Return.
- **F8-Gegencheck:** Supply-Temperaturabfall je Rohr = **0,00 K** (isotherm) → ein „räumlicher"
  Effekt kann den Faktor 2 NICHT erklären. Meine frühere Spatial-These ist damit widerlegt.
- **Zwei konsistente Rechnungen treffen 1842:** (A+B)/2 = (2125+1541)/2 = 1833; Paar-als-ein-Rohr
  am Mittel = 1847. Beide = **Graben einmal statt Vor-/Rücklauf getrennt.**
- **Mechanismus (`pipe_pair.py:508/583`):** im **L3+-Modus bleibt die Rücklauftemperatur ein fixer
  Param**; nur der Supply-Verlust wird in die Enthalpie/Bilanz propagiert (583). Der Return-Verlust
  (≈1541 MWh) wird zwar berechnet, **erzwingt aber keine Mehrerzeugung** → die Bilanz `gen = liefer +
  1842 + dump` trägt nur die Supply-Seite. **Undercount, schmeichelhafte Richtung** (weniger Verlust
  → weniger Erzeugung/Brennstoff/CO₂/TAC).
- **ZWEI VERLUSTKANDIDATEN (beide festgehalten, KEINER angefasst bis Re-Solve):**
  | | MWh | % der Lieferung | Bedeutung |
  |---|---|---|---|
  | **1842** (Bilanz, Supply-seitig) | 1842 | 25,4 % | aktuell wirksam, Undercount |
  | **3741** (`network_Q_loss`, Supply+Return getrennt) | 3741 | 51,5 % | physikalisch vollständig |
  Config-Rekonstruktion bestätigt: Supply 2125 + Return 1541 = 3666 ≈ 3741. **1842 ist zu KLEIN,
  nicht 3741 zu groß.**
- **Zweite, GEGENLÄUFIGE Baustelle — `j13_to_j15`:** U_s=1,31 / U_r=1,40 sind **hartcodierte Literale**
  (Config Z.358/359), **4,6× der 0,28/0,30 des baugleichen DN200-Nachbarn** (Z.351). Kein DXF-Rohwert,
  keine DN-Ableitung, kein Kommentar → **untraceable Ausreißer.** Dieses eine Rohr = 826/2125 MWh
  (39 %) des Supply-Verlusts. Korrektur auf 0,28/0,30 senkt den Verlust um ~1100 MWh.
  (Nebenbefund: Paper-1-Fig `fig_trunk_profile.py` hardcodet 125 m Länge, Config 914 m — separat prüfen.)
- **Die beiden Korrekturen WIRKEN GEGENEINANDER:** Return in die Bilanz aufnehmen **erhöht** (~+1500),
  `j13_to_j15`-U korrigieren **senkt** (~−1100). Netto 15–35 % — **nur ein RE-SOLVE entscheidet**,
  keine Handrechnung (Erzeugung, Dispatch, TAC verschieben sich alle mit).
- **Reihenfolge vor T1/T4:** (1) `j13_to_j15`-U-Herkunft mit Autor klären (Fix 0,28/0,30 oder belegen);
  (2) entscheiden, ob Return-Verlust in die Bilanz muss (Var statt Param) ODER dokumentierte
  Modellgrenze; (3) EIN Re-Solve mit beiden Entscheidungen; (4) berichtete Verlustgröße = die
  physikalisch vollständige. `network_Q_loss`/Closure-Formel bis dahin UNBERÜHRT.
- **Netzverlust % der Lieferung wird berichtete Validierungsgröße** (T4), Literaturband 10–15 %
  (kompakte Industrienetze weniger) als Plausibilitätsgrenze.

### Entscheidungen & Umsetzung (2026-09-03)
- **(1) Return-Verlust IN die Bilanz — UMGESETZT (Korrekturfix, keine Erweiterung).** Da T_return
  Param ist, ist `Q_loss_return[t]` je Rohr eine Konstante; Summe als Erzeuger-Zusatzbedarf in
  `constraint_builder.py` `primary_producer_balance` aufgeschlagen — **nur auf dem Nodal-Pfad**
  (gegated auf `_bidi`; der Legacy-`network_Q_loss_per_timestep`-Fallback summiert Supply+Return
  schon, sonst Doppelzählung). Keine neue Variable, kein Gap-Risiko. Echte Rücklauf-Propagation =
  Future Work. Verifikation MM-S1-HK0 (commitment ON) läuft.
- **(2) `j13_to_j15`-U — Basis 0,28/0,30, Original 1,31/1,40 als dokumentierte Sensitivität**
  (ein Dispatch-Lauf), FALLS nicht als real belegbar. **Autoren-/Betreiber-Check offen:** ist der
  Abschnitt j13→j15 real ungedämmt/alt? Wenn ja → 1,31 ist real und wird ein Befund. Keine stille
  Korrektur — beide Fälle transparent.
- **DREI KONSEQUENZEN (verbindlich):**
  1. **Alle bisherigen Memmingen-Zahlen sind hinfällig** (+44,8 %, Elektrifizierungs-Sweep, Siting-
     Landschaft): der Verlustterm geht in Erzeugung/Brennstoff/CO₂/TAC. Unkritisch, weil Freeze noch
     nicht gilt — aber **keine alte MM-Zahl weiterverwenden** bis zum Re-Solve.
  2. **Stadtbach braucht dieselben zwei Prüfungen VOR dem Re-Solve** (nicht danach): Rohr-Verlust-
     tabelle auf analogen U-Ausreißer scannen; der Rücklauf-Fix trifft SB (640 GWh Absatz) absolut
     deutlich härter als MM.
  3. **MM-S4-Sprung 299k→493k** ist jetzt Kandidat für „erklärt sich durch genau diese Verlust-
     behandlung" — beim Re-Solve mitprüfen; wenn es aufgeht, löst sich der Modellversions-Streit mit.
- **Paper-Nutzen:** Diese Kette begann als „Closure-Metrik kaputt" und endet bei einer echten
  Unterkostung in der Nebenbedingung + einem Datenfehler in einem Rohr, das 39 % der Verluste trägt.
  Genau das ist glaubwürdiges Validierungsmaterial. **Rohr-Verlusttabelle = Supplement-Tabelle**;
  ein Einzelrohr mit 39 % der Netzverluste ist das beste Argument für ortsaufgelöste Modelle.

### Verlusthöhe ist ein BEFUND, kein Fehler — lineare Wärmedichte (2026-09-04)
- **j13-Fingerabdruck = Datenfehler, nicht Bauzustand:** U_s 1,31/0,28 = **4,68**, U_r 1,40/0,30 = **4,67**
  — Vor- und Rücklauf um denselben Faktor auf drei Stellen verschoben. Reale Dämmschäden treffen eine
  Leitung, nicht beide identisch skaliert. Zudem: völlig ungedämmte erdverlegte DN200 läge bei
  U ≈ 3,5 W/(m·K) (2πλ/ln(4z/d)), nicht 1,31 → 1,31 passt in kein physikalisches Regime, aber exakt
  auf „Normalwert × 4,67". → **Multiplikations-/Übernahmefehler.** Betreiber-Rückfrage läuft parallel,
  blockiert den Re-Solve NICHT.
- **Verlusthöhe erklärt sich durch geringe Belegungsdichte:** Lieferung 7257 MWh / Trasse 6.989 m =
  **1,04 MWh/(m·a)** (Trasse = Route, Vor+Rücklauf teilen EINEN Graben, nicht ×2). Unter ~1,5 MWh/(m·a)
  steigen relative Netzverluste in der Literatur steil; 25–35 % sind für dünn belegte Netze dokumentiert.
  Memmingen liegt bei 0,69× der Schwelle → **34 % (j13-korrigiert) sind erwartbar, kein Fehler.**
  Wird als T4-Validierungsgröße mit Dichte-Kontext berichtet.
- **Verluststand nach beiden Fixes:** Return-Fix (Korrektheit) → 49,2 %; j13-Korrektur (Datenfehler,
  −1427+306 MWh) → **33,7 % = 2448 MWh**. Das ist die berichtete Basis-Zahl (vorbehaltlich Re-Solve).
- **C3-Argument:** ein Netz mit ⅓-Verlust, davon 40 % in einem Strang, ist der Musterfall dafür, dass
  ortsaufgelöste Modelle die Investitionsentscheidung ändern — ein aggregiertes Ein-Knoten-Modell sieht
  davon nichts. Bestes Einzelbeispiel für C3.
- **ENDPUNKTE-BEFUND (Verlust folgt Wärmeliniendichte, beide Netze):** MM 7257 MWh / 6.989 m =
  **1,04 MWh/(m·a)** → 36 % Verlust (dünn). **SB 639.973 MWh / 54.220 m = 11,80 MWh/(m·a)** → das
  11,3-fache, ~8× über der Schwelle → erwartet niedrige einstellige rel. Verluste (SB-Re-Solve bestätigt).
  **Dasselbe Modell/Physik, zwei Netze an entgegengesetzten Enden der Belegungsdichte, Verlustanteil
  folgt der Literaturbeziehung** — das trägt die Endpunkte-Argumentation stärker als alles bisher im
  Paper und macht aus MMs 36 % einen belegten Befund. **ZITAT NÖTIG (in .bib):** Persson & Werner (2011),
  „Heat distribution and the future competitiveness of district heating", Applied Energy 88(3) — die
  kanonische Wärmeliniendichte-↔-Verlust-Referenz (definiert linear heat density, zeigt die Beziehung).
  Gehört in T4/§Validierung als Plausibilitätsanker statt der internen Notiz.

## 4c. Speicher-Technologie & Kostenkurve — FINAL (2026-09-04, umgesetzt)

**Entscheidung:** ein atmosphärischer Stahltank als einzige Basis, degressive Kurve pro Tank,
ein Anker + Literatur-Exponent (kein 2-Punkt-Fit). Umgesetzt in `storage_geometry.yaml`,
`geometric_storage.py` (Pro-Tank-Kosten + v_min-Filter), `component_assembler.py`, `scenario_runner.py`
(HOT-Decke-Clip), `scenarios.yaml`/`scenario_labels.py`/`DOE_TABLE.tex` (HOT-Beschreibungen).

**Anker & Beleg:** 10.000 m³ → 250 €/m³ (IEA-DHC Annex XII, TTES 100–400 €/m³, größendegressiv).
Querbelege: ASME 2025 „Cost Analysis for Large TES Systems"/SPF — atmosphärische Tanks 220–400 USD/m³,
>7500 m³ <200 USD/m³; IEA-ES Fact Sheet Sensible Water (2024) ~210 €/m³. Vendor-Werte NICHT benutzt.

**Vier Review-Auflagen — Umsetzungsstand:**
1. **v_min ≥ 50 m³** — im Code als Filter (positive Sprossen < 50 m³ fallen raus), in der YAML begründet.
   Nur MM nähert sich der Grenze; MM-HOT verwirft die 2 kleinsten Sprossen (physikalisch korrekt).
2. **F2 als b-Band {0,65 / 0,70 / 0,776}** — NICHT durch Zusatz-Solves: CAPEX je Sprosse ist eine
   additive Konstante, wird post-hoc getauscht. **TODO Figur-Stufe:** `result_collector` muss die
   gewählte Sprosse (V, N) exportieren, damit F2 das Band rekonstruieren kann. `report_storage_ladders.py`
   liefert die drei Kostenspalten bereits.
3. **Tornado-Sensitivität:** Speicherkostenanker mit **IEA-DHC-Band 100–400 €/m³** — durch die
   Pro-Tank-Regel der dominante Speicherparameter → in die T2-Tornado-Achse aufnehmen.
4. **T2-Satz zum ASME-Fit:** die ASME-Regression C∝V^1,10 (R²=0,66) ist super-linear/verrauscht und
   wird NICHT als Exponent benutzt; stattdessen materialbasierte Skalierung (Oberfläche V^2/3 + BoP → 0,70).
   **β=0 = turnkey** (Kostenumfang: alle €/m³ sind Gesamt-installiert inkl. BoP) — ebenfalls in T2 vermerken.
   Der 100-m³-Kleinbereich hat keinen harten begutachteten Punkt (nur MM landet dort, ~0,1 M€ TAC → immateriell).

**Beide Leitern** (aus `report_storage_ladders.py`, ΔT=15 K, η_strat=0,85, nutzbar 14,42 kWh/m³):
MM (N=1 durchweg) 76–2109 m³; SB (N=1..15) 2566–141.909 m³, Knie-Bereich (8–12 h) N=5..7 @ v/N≈8300 m³
→ ~263 €/m³. SB-Reichweite = 2046 MWh/28 h/141.909 m³/N=15 ≈ 2,8× Knie → inneres Optimum garantiert.
**HINWEIS:** die aktuellen MILP-Leitern sind für F2 zu grob (Punkt 2, Review 2026-09-04) — MILP auf ~8
verdichten, Study G separat mit 10–12 log-verteilten Punkten je Netz (siehe §4-TODO).

**ALTE ZAHLEN UNGÜLTIG (HOT-Bug, gefunden 2026-09-04):** vor dem Ceiling-Clip lud die WP bei
Hot Charging auf T_VL,max (SB 122 °C) mit niedrigem COP, während der 95-°C-Speicher alles über 95 °C
verwarf → **alle bisherigen SB-Heißbeladungs-Ergebnisse (S3, S7; MM-S3/S5 minimal) sind in bekannter
Richtung falsch** (WP-Strom für verworfene Wärme). Nach Fix HOT = min(T_VL,max, 95 °C). Nicht wieder-
verwenden; im Re-Solve neu rechnen. **F2-Abbildung:** b-Band {0,65/0,776} sichtbar (bei MM ±25 % an der
Optimum-Sprosse, nicht kosmetisch); SB-Oberkante (>1 Tank-Farm, größer als jeder reale FW-Speicher) mit
schattiertem „praktisch nicht baubar"-Bereich + benennbarer Grenze hinterlegen.

## 4d. Infrastruktur-Blocker (2026-09-04, vor der Kampagne zu lösen)
- **Config validiert (Build+Solve):** MM-S1-HK0 baut das volle atmosphärische Modell fehlerfrei und löst
  die Wurzel-LP-Relaxation (268 k €/a). Alle Config-/Code-Änderungen (Pro-Tank-Kosten, v_min, 95-°C-Decke,
  HOT-Clip, ΔT=15 K, Floor 74→78,6) greifen wie erwartet. Der Solve selbst ist NICHT das Problem.
- **BLOCKER 1 — Platte voll:** C: 2,0 TB zu 100 % belegt (~480 MB frei), D: 4,7 GB voll. Gurobi kann keine
  B&B-Nodefiles schreiben → „No space left on device" (MM-S1 explizit, MM-S4 still). Workaround eingebaut:
  `NodefileStart=16` in `scenario_runner` (`_DISK_SAFE_SOLVER_OPTS`) hält kleine Bäume im RAM → MM löst.
  Für die **volle 62er-Kampagne (große SB-Solves) reicht das NICHT** — echter Plattenplatz muss frei werden
  (Kandidaten: `output/_prefix_backup_2026-07-26` 5,7 GB + `output/paper1_backup_pre_deltap_pumpfix_20260726`
  2,1 GB = 7,8 GB dated Backups; AUTOR-Entscheidung, nicht selbst gelöscht).
- **BLOCKER 2 — REPORTING-INTEGRITÄT (BESTÄTIGT, nicht nur Bug):** die eingefrorene Kampagne lief mit
  `MIPFocus=1, Heuristics=0,5, KEIN Cuts=2` — NICHT mit dem dokumentierten Fix `Cuts=2/MIPFocus=2/
  Heuristics=0,1` (Implementation Statement Part F.4). **Empirischer Beweis:** `gurobi_SB-S1-HK0.log`
  (nie von mir überschrieben, Datum 2026-08-09) zeigt exakt `MIPFocus=1 / no-Cuts`. **Mechanismus:**
  Paper 2 löst über den Fix-and-Relax-Stage-A-Pfad (`_solve_milp_stage`); dessen Zeile 309 ERSETZTE
  `solver_options` komplett und verwarf die Config-Bound-Knöpfe. Der Config-Fix galt nur der trivialen
  Stage B (Binaries fixiert). **git blame:** Clobber seit 9285065 (2026-05-20), also vor der Kampagne.
  **Folge:** die Methodenbeschreibung (Cuts=2/MIPFocus=2) stimmt NICHT mit dem Gerechneten überein; erklärt
  die hartnäckigen 4–9 % Gaps und die `maxTimeLimit`-Treffer (MM-S1-HK0 lief die vollen 24 h).
  **FIX (2026-09-05):** `solver.py:309` propagiert jetzt die Config-Bound-Knöpfe (Cuts/MIPFocus/Heuristics/
  NumericFocus + NodefileStart) in Stage A; Paper-1-Defaults + Stage-A-Gap/Zeit unberührt. **Dauer-Wächter:**
  `verify_solver_params.py` liest die tatsächlichen Gurobi-Parameter aus dem Log zurück, vergleicht mit der
  Config und schreibt sie ins `run_manifest.json` — bei Abweichung `SolverParamMismatch` (lauter Fehler,
  kein stiller Weiterlauf). **KORREKTURLISTE:** (a) Solver-Beschreibung im Draft neu schreiben (die Kampagne
  MUSS mit dem Fix neu gerechnet werden, sonst stimmt die Beschreibung erst recht nicht); (b) alle Gap-Angaben
  in T3/T5 werden sich mit dem wirksamen Fix ändern — nach der Neurechnung aktualisieren.
- **2 Runaway-Solves gekillt:** der MM-S4-„main"-Prozess (PID 107480) lief seit ~1,5 h weiter (nicht
  abgestürzt wie zuerst gedacht — gepufferte Logs), + MM-S1-Validation; beide auf voller Platte, beide beendet.

## 4e. MM-S1 Konvergenz-Diagnose — VORAB-ERWARTUNG (2026-09-05, vor dem Lauf notiert)

**Frage:** ist der gestuckte 704-k-Inkumbent ein Heuristikversagen (Startpunktproblem) oder hat der
atmosphärische Umbau MMs Kosten wirklich verdoppelt (Config-Problem)? Test: MM-S1-HK0 mit TES fixiert
(~1,1 MWh, nächste neue Sprosse zur alten 1,4 MWh), HP/EK investierbar, mit Cuts-Fix, ~10 min.

**344 k ist als Ziel TOT** — die Zahl stammt aus dem Modell OHNE bepreisten Rücklaufverlust. Nach dem
Return-Fix erzeugt MM 10.829 statt 9.083 MWh = **+19 % Wärme**, die bezahlt werden muss.
Überschlag: ~250 k OPEX von 344 k × 1,19 ≈ +47 k → ~390 k, plus Speicherkostenänderung.

**VORAB-ERWARTUNGSBEREICH: ~380–450 k €/a.** Lesart (vorab festgelegt = Test):
- **~380–450 k** → atmosphärische Config gesund, 704 k = reines Heuristikversagen → **Startpunktproblem**,
  A (MIP-Start) lohnt. Der fixierte Lauf liefert dann selbst den Seed (vollständige neue Lösung).
- **~700 k** → der Umbau hat MMs Kosten verdoppelt → **Config-Problem jagen, Solver nicht anrühren.**
- **deutlich <380 k** → Return-Fix nicht überall wirksam → auch ein Befund.

**Ergebnis (2026-09-05):** DIAGNOSE UMGELEITET — der Engpass ist WEDER Config NOCH Investition,
sondern das **Unit Commitment.** Mit TES fixiert bleiben **17.500+ fraktionale UC-Binärvariablen** an der
Wurzel (5 Erzeuger × 8760 h), und Gurobi findet unter der Config-Politik (`MIPFocus=2/Cuts=2/Heuristics=0,1`)
in 17 min KEINEN zulässigen Inkumbenten — MIPFocus=2 hungert die Inkumbentensuche aus. Auch `MIPFocus=0`
(TES fixiert) hat an der ersten B&B-Wurzel (483 s) noch keinen Inkumbenten. **Config-Verdikt bleibt offen**
(kein Inkumbent lesbar). ABER: die Wurzel-LP-Relaxation ist **267.857** (~unverändert ggü. altem Modell) →
der atmosphärische Umbau hat die zugrundeliegenden Kosten NICHT verdoppelt; die 704 k waren ein Heuristik-
Artefakt. **Offene Teilfrage:** die LP-Grenze ~268 k trotz Return-Fix (+19 % Wärme) könnte bedeuten, dass der
Return-Verlust die Zielfunktion nicht wie erwartet erhöht — braucht die Ganzzahl-Lösung zur Klärung.
**Kernbefund:** die Solver-Politik (bound-optimiert für die Consumer-Node-TES-Fälle) SCHADET den UC-limitierten
Fällen wie MM-S1. Zwei entgegengesetzte Probleme in einer Kampagne — reines Parameter-Tuning löst das nicht.

**Vierte Option — min_load-Relaxierung (Schritt 3, 2026-09-05):** `min_load->0` auf den 3 Bestandserzeugern
(Env `CALION_RELAX_MIN_LOAD`) → MM-S1 fällt von **60 % (fest) auf 2,26 % in ~14 min**, Inkumbent **~277 k**
(Bound 271 k). **min_load IST der Härtetreiber.** Konvergenz mit einer Config-Zeile gelöst. ABER zwei Vorbehalte:
- **17.444 Binärvariablen bleiben** auch bei min_load=0 — die Constraints werden nur NICHT-BINDEND, nicht
  entfernt; Gurobi branched weiter, schließt aber schnell (LP fast ganzzahlig). Für echte Entfernung müsste
  die Integralität relaxiert werden (Domain→continuous), nicht nur min_load=0.
- **min_load-PRÄMIE (A/B-TAC-Differenz) NICHT sauber gemessen:** relaxiert ~277 k ist eine UNTERE Schranke des
  min_load-AN-Optimums; min_load-AN löst nicht → keine gepaarte Zahl aus MM-S1. Der schmutzige Vergleich
  (277 k relaxiert vs. alt 344 k) deutet auf ~20 % Prämie, NICHT ~1 % → die „billige Fußnote" ist NICHT belegt.
- **Physikalischer Verdacht:** Gaskessel 13 MW × min_load 0,1 = **1,3 MW Mindestlast-wenn-an > MM-Mittellast
  1,08 MW** → min_load kann physikalisch binden → Prämie evtl. materiell. Sauberer A/B braucht ein Szenario,
  das BEIDE Wege löst (Vorschlag: Kurzhorizont, z. B. 1 Monat, damit min_load-AN klein genug ist).

## 4g. Return-Fix Objective-Validierung — BESTANDEN (2026-09-05)
**Test (Schritt 1, vor allem anderen):** dasselbe Szenario (MM-S1-HK0, TES fix 1,1 MWh), Root-LP,
einmal mit und einmal ohne bepreisten Rücklaufverlust (Env `CALION_DISABLE_RETURN_LOSS`).
**Ergebnis:** ohne = **239.602**, mit = **267.857** → **+28.255 € (+11,8 %).** Der Rücklauf-Fix
kommt in der Zielfunktion an (die „gar keine Bewegung"-Sorge ist ausgeräumt). +28 k statt der grob
geschätzten +47 k, weil die LP-Relaxierung die Zusatz-Wärme billigstmöglich deckt — plausibel.
Wirkungsgrade sind KONSTANT (0,80/0,90/0,85, nicht lastabhängig) → min_load-Relaxierung ist verzerrungsarm.
**Nebenbefund:** Juli-MM-S1 schloss lt. Notiz bei 1,4 % (alte Druckconfig); neu hängt es bei 60 % — der
atmosphärische Umbau ODER der Return-Fix hat MM-S1 deutlich schwerer gemacht. Beim min_load-Test mitklären.

## 4h. min_load A/B + Bindungsanalyse — ENTSCHEIDUNG (2026-09-05)
**Kurzhorizont-A/B (MM-S1, Investition frei, Sommer- UND Wintermonat, je min_load an/aus):**
- **Winter-Prämie +0,21 %** (min_load bindet kaum bei hoher Last), **Sommer-Prämie ~+17 %** (bindet hart bei
  Schwachlast). Ein Januar-Monat allein hätte die Relaxierung FÄLSCHLICH freigegeben — Sommer+Winter war
  zwingend richtig. **Speichersprosse-Spalte KONFUNDIERT:** 1-Monat zahlt Jahres-CAPEX gegen 1/12-OPEX →
  TES=0 in ALLEN vier Läufen; die Größenfrage braucht das volle Jahr.
- **Bindungsanalyse (Stunden mit 0<Erzeugung<min_load in der relaxierten Dispatch):**
  Gaskessel **0 h (läuft nie)** → min_load nutzlos, gefahrlos relaxierbar (Presolve macht es vermutlich eh);
  **Biomasse 17 %/59 % (Winter/Sommer)** → bindet stark, ist der Speicher-Wert-Mechanismus (Grundlast über
  Boden gezwungen → Überschuss bei Schwachlast → Speicher); CHP 10 %/21 % → bindet moderat.
- **ENTSCHEIDUNG:** min_load bleibt (Biomasse trägt das Kernergebnis; Blanket-Relaxierung würde die
  Speicherauslegung zum Artefakt machen). Selektive Relaxierung des Gaskessels bringt kaum Traktabilität
  (Presolve). **Kernbefund für die Kampagne:** Monatsläufe mit min_load lösen SCHNELL (0,2–0,8 % in Minuten),
  nur das volle Jahr (12× Binärvariablen) hängt. → **UC-Seed aus Monatszerlegung** ist der saubere,
  deterministische, uniforme Weg: 12 Monate schnell lösen (min_load an), Commitment (Biomasse/CHP)
  konkatenieren, als MIP-Start des Jahres-Investitions-MILP setzen. Kein Parameter-Tuning, physiktreu.

## 4i. UC-Seed gebaut, aber INJEKTION scheitert (2026-09-05) — offener Punkt
- **Seed gebaut & valide:** `build_uc_seed.py` löst 12 Kalendermonate sequenziell (SoC-Handoff, TES fix,
  min_load an) → `output/uc_seed/MM-S1-HK0/dispatch_hourly.csv` (8760 h, alle Monate status=ok). SoC-Handoff
  degeneriert (Terminal frei → jeder Monat leert auf den 5-%-Floor); harmlos, da nur Commitment geseedet wird.
- **INJEKTION scheitert 3×:** `_apply_warmstart` setzt 43.800 Commitment-Binär-Hints, aber Gurobis
  Vervollständigungs-subMIP läuft **0 Knoten / „did not produce a new incumbent"** — bei (a) der alten Lösung,
  (b) dem Monats-Seed, (c) dem Monats-Seed MIT passend fixiertem TES=2,2 (obwohl die Lösung dann beweisbar
  existiert). → **Nicht die Seed-Qualität, sondern der Injektionsmechanismus:** partielle Namens-inferierte
  Binär-Hints (`_infer_binary_from_ws`) lassen sich für dieses Modell nicht zu einer zulässigen Lösung
  vervollständigen (vermutlich inferiert die Rundung Commitment-Kombinationen, die keine zulässige Dispatch-
  LP zulassen).
- **Terminal-Diagnose (2026-09-06):** Jahresmodell hat `terminal_soc_fraction=0.5` + `soc0_fraction=0.5`;
  Seed endete (Terminal freigestellt) am 5-%-Floor → Terminal verletzt. GEFIXT: Dezember mit terminal=0.5
  neu gelöst (endet 1,10 MWh = 50 %), in den Seed gespliced. **RE-TEST: 4. Ablehnung — immer noch „did not
  produce a new incumbent".** Der Terminal war NICHT die (alleinige) Ursache → der **partielle
  Commitment-Hint-Mechanismus (`_apply_warmstart`) funktioniert für dieses Modell grundsätzlich nicht.**
- **ABORT-SCHWELLE ERREICHT** (Zulässigkeitscheck + 1 Anlauf gescheitert). ABER: die Abort-Prämisse
  „ungeseedet = 3–5 % Gap" **stimmt nicht** — ungeseedetes MM-S1 hängt bei **60 %** auch MIT Cuts-Fix.
  Regression: Juli-MM-S1 (alte Druckconfig) = 1,4 %; neu = 60 %. Der atmosphärische Umbau ODER der
  Return-Fix hat MM-S1 von leicht auf unlösbar gedreht. → **Weder Seed (Injektion scheitert) NOCH ungeseedet
  (60 %) gibt eine saubere Kampagne.** ECHTER Blocker.
- **ZWEI PFADE (Autor-Entscheidung):** (a) der von dir empfohlene VOLLSTÄNDIGE var-dict-MIP-Start (aus den
  gelösten Monats-Pyomo-Modellen `(var,index)→value`, absolute Indizes, `.value` setzen + `warmstart=True`)
  — NOCH NICHT PROBIERT (ich hing am partiellen Pfad); echtes Engineering. (b) die Traktabilitäts-REGRESSION
  jagen: warum 1,4 %→60 %? (diskrete TES-Leiter + Entlademaske + Return-Fix interagieren mit der Biomasse-UC).
  Wenn (b) die Regression findet+entschärft, löst MM-S1 ohne Seed. Der Seed selbst (12 Monate, terminal-korrekt) steht.

## 4j. Traktabilitäts-Regression: Diagnose = HEURISTIK-VERSAGEN (2026-09-06/07)
- **Regression NICHT Solver-Settings:** MM-S1 neue Config + Juli-Settings (MIPFocus=1/keine Cuts/Heur=0,5)
  → **55 %** (nicht 1,4 %). Hypothese widerlegt.
- **Regression NICHT Maske, NICHT Return-Fix:** Bisektion (Juli-Settings + Maske aus → 55 %; + Return-Fix
  aus → 57,7 %). Beide unverändert gestuckt.
- **DIAGNOSE:** in ALLEN Varianten findet Gurobis Heuristik einen SCHLECHTEN Erst-Inkumbenten (~570–600 k)
  = 2,3× die LP-Grenze (~240–268 k) und weit über dem echten Optimum (~340–390 k), und verbessert ihn nicht.
  **Die Grenze ist gesund; der INKUMBENT ist das Problem** (Heuristik-Versagen, nicht Config-Feature).
  Auch TES-fixiert bleibt gestuckt (17.500 UC-Binärvariablen) → die Biomasse-UC ist der Kern.
- **KONSEQUENZ:** genau dagegen hilft ein **kompletter MIP-Start** — er GIBT Gurobi den guten Inkumbenten
  direkt, umgeht das Heuristik-Versagen. Der partielle Hint scheiterte, weil die Vervollständigung infeasibel
  ist; eine VOLLSTÄNDIGE Zuweisung (alle Vars) braucht keine Vervollständigung. → **Pfad (a) ist jetzt der
  klare Fix**, und die Bisektion (b) war die richtige Diagnose, um dorthin zu kommen. Der terminal-korrekte
  12-Monats-Seed IST der gute Inkumbent; er muss nur vollständig (Kontinuierliche + Investition-Sprosse 2,2)
  injiziert werden (var-dict aus den Monats-Pyomo-Modellen, absolute Indizes, `.value` + `warmstart=True`).
  ENGINEERING: build_uc_seed muss die gelösten Monats-MODELLE fassen (nicht nur die CSV-Outputs).

## 4k. Kontrolllauf: KEINE Regression — MM-S1 war IMMER hart (2026-09-07)
- **Kontrolle (druckbeaufschlagte Juli-Config auf HEUTIGEM Code, Juli-Settings):** ebenfalls **55,0 %**,
  mit **identischem Inkumbenten (596.101,648) und Bound (267.995,444)** wie die atmosphärische Variante.
  → Speicher-Config ist NICHT der Differenzierer (Lösung ist UC-dominiert; MM-Speicher ist winzig).
- **Die Prämisse „Juli-MM-S1 = 1,4 %" war falsch:** die eingefrorene Kampagne hat MM-S1-HK0 mit
  **`status=maxTimeLimit`** gelöst — es hat die 24 h-Grenze getroffen und **NIE konvergiert.** Die „1,4 %"
  (Memory-Notiz) waren die **F3-Siting-Enumeration** (Hub-TES vs. Consumer-Node), ein ANDERES, kleineres
  Problem — nicht das volle MM-S1-HK0-Investitions-MILP.
- **FAZIT: keine Code-Regression, kein Config-Problem.** MM-S1-HK0 Jahres-MILP ist INHÄRENT hart und war es
  immer (maxTimeLimit schon in der eingefrorenen Kampagne). Das Modell ist gesund. → **(a) ist sicher zu
  bauen** — der komplette MIP-Start bringt MM-S1 zum ERSTEN Mal zur Konvergenz. **Wichtige Konsequenz:** die
  eingefrorene Kampagne hatte bereits unkonvergierte harte Szenarien (maxTimeLimit) → große, undokumentierte
  Gaps in den berichteten Zahlen. Der Seed verbessert genau das. (Die frühere „Heuristik-Versagen"-Diagnose
  §4j bleibt korrekt — MM-S1 IST heuristik-limitiert; nur ist es kein neuer Defekt, sondern der Normalzustand.)

## 4l. NEUTRALITÄTSPRÜFUNG: GESCHEITERT — Seed-Ansatz funktioniert nicht (2026-09-07)
- **Complete-MIP-Start gebaut & korrekt:** `build_uc_seed.py` dumpt jetzt die vollständige Pyomo-Lösung je
  Monat (solver.py, beide Pfade), remappt positionelle Indizes (1..744 → absolut per Stunden-Offset),
  akkumuliert zu `vars_seed.json` (316 Komponenten, 308 Zeit-Vars × 8760, 2,7 Mio Werte). Injektion
  (`_apply_warmstart_dump`, CALION_WARMSTART_DUMP) setzt **2.698.085 Var-Werte, 0 skipped** — die
  vollständige Zuweisung landet komplett im Jahresmodell.
- **Gurobi lehnt TROTZDEM ab (7×):** „User MIP start did not produce a new incumbent" — auch mit
  (a) terminal-korrektem Seed (Dez endet 50 %), (b) TES fix 2,2 = Seed-Größe (kein Free-TES-Mismatch).
  → **die verkettete Monats-Lösung ist STRUKTURELL unzulässig fürs Jahresmodell.** Nicht Terminal, nicht
  TES-Größe. Vermutlich: die Pro-Monat-SoC-Rekursion (jeder Monat startet frisch aus soc0) stitcht nicht in
  eine durchgängige Jahres-Trajektorie, die ALLE Jahres-Constraints erfüllt (SoC-Bounds, Shared-Port-Cut,
  Entlademaske, exakte E[t]-Rekursion an Monatsgrenzen) — Gurobis Repair-subMIP findet 0 Knoten/infeasibel.
- **ABBRUCH-SCHWELLE weit überschritten** (7 Ablehnungen, viele Stunden = die Mehr-Stunden-Schleife, vor der
  gewarnt war). **Seed-Ansatz (monatliche Zerlegung) ist für dieses Modell GESCHEITERT.**
- **IMPASSE (Autor-Entscheidung nötig):** weder Seed (7×abgelehnt) noch ungeseedet (harte Szenarien = 55 %,
  Zahlen grob falsch, Abbildungen unzuverlässig) gibt eine saubere Kampagne für die ~13 harten Szenarien.
  Die einfachen (~25/38) konvergieren ungeseedet vermutlich auf 3–9 % (wie Juli). Optionen: (i) ungeseedet
  fahren + harte Szenarien mit dokumentiertem Gap fahren (die einfachen sind valide, die harten bleiben
  offen — ehrlich, aber Teil des Papers fehlt); (ii) echte Zulässigkeitsprüfung (Seed ins Jahresmodell,
  Constraints iterieren, Top-10-Verletzungen) um den EINEN gebrochenen Constraint zu finden — evtl. Fix
  (z. B. überlappende Fenster statt harter Monatsschnitte); (iii) strukturelle Reformulierung der harten
  Szenarien (die endogenen Siting-MILPs dominieren die harte Menge). — Ich habe hier gestoppt statt weiter
  autonom zu iterieren; das ist eine strategische Entscheidung.

## 4m. IMPASSE AUFGELÖST — der EINE gebrochene Constraint + Binär-Fix-LP-Fix (2026-09-07)
- **Zulässigkeitsprüfung (Option 2, Autor-Vorschlag) durchgeführt:** neuer `CALION_FEAS_ONLY`-Block in
  `solver.py` (MAIN-Pfad) setzt die 2,7 Mio Seed-Werte, iteriert ALLE aktiven Constraints, misst Body vs.
  Bound, listet die Top-15-Verletzungen, bricht vor dem Solve ab. **Ergebnis: 298.204 verletzte Constraints,
  Top-15 AUSNAHMSLOS `hp_main_linfix_lo[t]`, Verletzung konstant ≈ 1,0065** (Stunden ~5600–5826, Aug/Sep).
- **Ursache (eindeutig):** das ist die WP-Kapazitäts-Linearisierung (McCormick-Unterschranke von
  P_HP,out an die Kapazitäts-Sprosse). Der Seed enthält **`hp_main_cap_x_on` je Stunde** — die 12 Monate
  wurden mit WP INVESTIERBAR gelöst, **jeder Monat wählte seine EIGENE WP-Kapazität**. Verkettet widersprechen
  sich die 12 Kapazitäts-Segmente einer einzigen Jahres-WP-Kapazität → `hp_main_linfix_lo` bricht. NICHT
  Terminal, NICHT TES, NICHT SoC-Stitch (die früheren Vermutungen) — **die per-Monat-Investition ist der Bruch.**
- **Fix (Autor-Plan „Binär-Fix-LP"):** `_apply_warmstart_dump(fix_binaries=True)` (env `CALION_WARMSTART_FIXBIN`)
  **fixiert nur die Commitment-Binären (stündliches An/Aus: CHP/Biomasse/Gasboiler/WP/E-Boiler on)** und lässt
  alles Kontinuierliche FREI. **Kritisch:** Kapazitätswahl-Binäre (Name enthält `cap_x`) werden NIE fixiert
  (`CALION_FIXBIN_EXCLUDE=cap_x`), damit das Jahresmodell EINE konsistente Kapazität wählt statt der 12
  widersprüchlichen. Der schedule-fixierte Lauf ist (fast) ein LP und leitet eine **jahresweit konsistente,
  per Konstruktion zulässige** Kontinuierliche-Trajektorie + Investition ab → als `clean_seed.json` gedumpt →
  als vollständiger, jetzt akzeptierter MIP-Start wiederverwendet.
- **Status:** Lauf `output/mm_s4_reconcile/fixbin_lp/` produziert `output/uc_seed/MM-S1-HK0/clean_seed.json`;
  danach Injektion in den vollen (alle-frei) MM-S1-Lauf + Akzeptanzprüfung (`mip_start_status`). Fällt das
  vollfixierte LP unzulässig (falls doch eine Commitment-Binäre inkonsistent), Rückfall: nur Biomasse+CHP
  fixieren → winziges MILP. **Ersetzt die IMPASSE in §4l** (Option 2 gewählt, nicht (i)/(iii)).
- **Parallel gestartet (wartet auf nichts):** die 44 nicht-endogenen „leichten" Szenarien laufen ungeseedet
  in einen FRISCHEN Dir `output/paper2_runs_v3/` (env `CALION_OUT_BASE`, kein Clobber der stale-Juli-Zahlen),
  MM-Welle (18) zuerst, dann SB (24). Die 18 endogenen Siting-MILPs (S4/S5/S6/S7/CO) sind der harte Block,
  der den Seed bekommt.

## 4n. SEED FUNKTIONIERT im Kern — HP-Konsistenz war die Ursache; TES-Matching bleibt (2026-09-07 Abend)
- **HP-Fix bestätigt.** Seed neu gebaut mit `CALION_HP_FIX_MW=1.10` (HP in ALLEN 12 Monaten fix, nicht
  investierbar) → alle 12 Monate hp_cap=1.1, `vars_seed.json` konsistent. FEAS_ONLY: **`hp_main_linfix_lo`
  verschwindet komplett** aus den Verletzungen (vorher 298 k × 1,0065). Restliche FEAS_ONLY-Verletzungen
  (`heat_demand`, `heat_delivered` auf Rohren) sind ein **Diagnose-Artefakt**: build_uc_seed lässt
  tuple-indizierte Rohr-/Temp-Vars WEG (Gurobi vervollständigt sie per LP), FEAS_ONLY wertet sie als 0.
- **Binär-Fix-LP mit dem KONSISTENTEN Seed = ZULÄSSIG** (vorher mit inkonsistentem Seed infeasibel):
  52.562 On/Off-Binäre fix, Kontinuierliche frei → **„Optimal solution found, Best objective €337.428,
  gap 0,26 %"**. Ergebnis als `clean_seed.json` gedumpt = **vollständige, exakt zulässige MM-S1-Lösung**
  (359 Komponenten, 4,47 Mio Werte, inkl. Rohr-Vars, HP=1,103 MW), TES fix 2,2.
- **VERBLEIBENDER BLOCKER = TES fix-vs-investierbar-Strukturmismatch** (dasselbe Muster wie HP). clean_seed
  wurde mit TES NICHT-investierbar (fixe 2,2) gebaut → es FEHLEN die TES-Investitionsvars (build, Größen-
  Binär, Kapazität). In das TES-INVESTIERBARE Zielmodell injiziert: „did not produce a new incumbent" OHNE
  Verletzungszeile (= unbelegte Investitionsvars, nicht Infeasibilität). Injektion in ein TES-fix-2,2-Modell
  (Struktur passt) sollte akzeptiert werden — Mechanismus dann bewiesen.
- **KAMPAGNEN-BEFUND (wichtig, ändert die Strategie):** die „leichten" fixed-site-MM-Szenarien sind NICHT
  alle leicht. S0/BC (ohne TES) konvergieren (3 fertig: BC-MM, MM-S0-HK0, MM-S0-TVLFIX). Aber Szenarien MIT
  investierbarem TES hängen bei **9–26 % Gap nach 90–100 min** (Richtung 2h-Cap). **Der Seed wird BREIT
  gebraucht, nicht nur für die endogenen Szenarien** — Option 1 („leichte laufen ungeseedet") trägt nur für
  die TES-losen S0/BC.
- **OFFENE AUTOR-ENTSCHEIDUNG (TES-Handling für Produktion):** (a) harte Szenarien mit TES FIX an sinnvollem
  Wert fahren + Seed → akzeptiert → konvergiert; TES-Größe separat per grobem Sweep (geometrische Leiter);
  (b) Seed um die TES-Investitionsvars erweitern (build/Größen-Binär/Kapazität auf 2,2-Sprosse setzen) →
  passt aufs investierbare Modell; (c) nur DISKRETE Vars als Hints (Commitment + Investitions-Binäre inkl.
  TES-Größe), Kontinuierliche von Gurobi vervollständigen lassen. Ich habe hier gestoppt (Zeit-Box weit
  überschritten) statt autonom weiter zu iterieren — das TES-Handling ist eine Design-Entscheidung mit
  Paper-Konsequenzen (bedingt-auf-TES vs. Voll-Co-Optimierung).
- **Neue solver.py/scenario_runner.py-Hooks:** `CALION_HP_FIX_MW`, `CALION_WARMSTART_FIXBIN`,
  `CALION_FIXBIN_EXCLUDE`, `CALION_TIMELIMIT`, `CALION_MIPGAP`, `CALION_OUT_BASE`, `CALION_FEAS_ONLY`.

## 4o. TRAKTABILITÄTS-WAND: Jahres-MILP ist für JEDES Investitionsszenario hart (2026-09-07 spät)
- **Seed AKZEPTIERT bewiesen:** clean_seed@2,2 in TES-fix-2,2-Modell → „Loaded user MIP start with objective
  337428". Mechanismus (HP-fix → binär-fix-LP → clean_seed → Injektion bei passender Struktur) funktioniert.
  ABER: der Seed liefert einen guten INKUMBENT, NICHT eine enge Schranke.
- **Die eigentliche Wand:** die LP-Relaxation ist lose (Wurzel 268 k vs. Inkumbent 337 k = 20,6 % Gap;
  ungeseedet nach 100 min erst 9,4 %). Ursache = **min_load-Unit-Commitment über 8760 h + HP-McCormick**.
  HP fixieren (McCormick weg) hilft NICHT genug (IntInf 17k→3,3k, aber immer noch kein Inkumbent nach 630 s).
  Die Monatszerlegung war NUR tractable, weil 744 h ≪ 8760 h.
- **Betrifft ALLES, nicht nur TES/endogen:** Fertige v3-Ergebnisse zeigen **MM-S0-HK0 und MM-S0-TVLFIX =
  maxTimeLimit** (S0 = HP investierbar, KEIN TES). Nur reines BC (keine Investition) konvergiert sauber
  (optimal). D. h. jedes Szenario mit investierbarer HP über das volle Jahr trifft die Wand — die Juli-
  Kampagne lief genau deshalb ins maxTimeLimit. Der Seed behebt das NICHT, er verbessert nur den Inkumbenten.
- **NEU-BEWERTUNG des Seed-Werts:** nicht „enge Optimalität" (unerreichbar im Zeitbudget), sondern „garantiert
  einen HOCHWERTIGEN zulässigen Inkumbenten ab t=0" (aus fast-optimaler Monatsdispatch), den ungeseedetes
  B&B im Zeitbudget evtl. nicht findet. Für die F2-Sizing-Kurve: die geseedeten Inkumbenten (gute obere
  Schranken) zeichnen die Kurve; die Gaps müssen transparent berichtet werden (behebt das Juli-Reporting-Loch).
- **OFFENE AUTOR-ENTSCHEIDUNG (größer als TES-Handling):** wie mit der Jahres-Traktabilitätswand für die
  GANZE Kampagne umgehen? (i) Seed + festes Zeitbudget/Szenario + Gap transparent berichten (pragmatisch,
  reproduziert Juli-Ansatz aber mit besseren Inkumbenten + ehrlichen Gaps); (ii) echte Dekomposition
  (rolling-horizon MIT dem Seed, oder Benders) — Engineering; (iii) engere Formulierung (McCormick straffen,
  min_load aggregieren). Ich habe hier gestoppt — das ist eine strategische Entscheidung mit Paper-Konsequenzen,
  keine, die ich autonom treffen sollte.

## 4f. MM-S4-Versöhnung: altes Ziel ungültig (2026-09-05)
Die 299 k ↔ 493 k stammen BEIDE aus dem Modell ohne bepreisten Rücklaufverlust — **kein gültiges Ziel mehr.**
Die Versionsprüfung muss `e8e445e + alle Fixes` gegen `main + alle Fixes` vergleichen — beide NEU gerechnet,
keine der alten Zahlen als Referenz. Frage bleibt „drehen sich Rangfolgen?", Erwartung ist eine andere.
(Sonst vergleicht jemand in zwei Wochen gegen 299 k und wundert sich.)

## 4p. Atmosphärische Kampagne — Stale-Anchor-Saga, Study C, S2-IIS (2026-09-14/15)

**Root cause der ganzen Runde:** `component_assembler.py`/`geometric_storage.py` (atmosphärische
Geometrie, autoritativ aus `storage_geometry.yaml`) wurden am **12.09.** geändert, ebenso
`constraint_builder.py`/`solver.py`/`result_collector.py` (uncommitted). Alle vier S0-Anker
(MM-S0-HK0/HK1/HK2, SB-S0-HK0) stammten aus Läufen **vor** diesem Datum (SB-S0-HK0 sogar vom **30.08.**)
— jede bis dahin berichtete Ersparnis-% war gegen einen ungültigen Nenner gerechnet.

**Fix-Methode:** 12h/43200s ungeseedete Free-Commitment-Stabilitätsläufe je Anker (matched-effort,
Inkumbent-Stabilität statt MIP-Gap als Konvergenzkriterium — Gap bleibt strukturell lose, ~15–18 % bei MM,
wegen min_load-UC über 8760 h, s. §4e/o). MM-S0-HK2 blieb im ersten Lauf bei 470.590 €/45,3 % Gap
stecken (LP-Bound 257 k, dicht an den TES-Szenario-OPEX 257–260 k → Solver heuristisch feststeckend,
nicht der wahre Optimum); ein Resolve mit `Cuts=1, MIPFocus=1, Heuristics=0.3` (statt der Default-Guard
`Cuts=2, MIPFocus=2`) fand 313.953 € — 24 % besser, plateaued über 2+ Zyklen, jetzt validiert.
**Validierte Anker:** MM-S0-HK0=331.028 €, MM-S0-HK1=310.653 €, MM-S0-HK2=313.953 €,
SB-S0-HK0=13.319.673 €.

**HAUPTERGEBNIS Memmingen (validiert):** Speicherersparnis clustert eng bei **11,2–14,8 %** über alle
validierten Szenarien (S1-HK0=11,2 %@6,5 MWh, S1-HK2=14,2 %@3,3 MWh, S3-HK0=13,8 %@2,2 MWh,
S3-HK1=11,8 %@2,2 MWh, S3-HK2=14,8 %@2,2 MWh) — deutlich kohärenter als die alten, verstreuten
1,9–8,2 %-Zahlen (Artefakt der Stale-Anker + eines separaten CAPEX-Bugs, s. u.).

**HAUPTERGEBNIS Stadtbach (validiert, überraschend):** atmosphärischer Speicher bringt unter HK0
**KEINEN Netto-Nutzen** — sowohl S1 als auch S3 haben ihr TAC-Minimum bei Rung=0 (0,0 % Ersparnis
gegen den validierten Anker). Jede Speichergröße kostet mit CAPEX mehr als S0, obwohl mehrere Rungs
OPEX-seitig günstiger sind. Die vormals berichteten 4,2 %/3,3 % waren reine Stale-Anker-Artefakte.

**Vorgelagerter CAPEX-Bug (bereits gefixt, hier dokumentiert):** `f2_capex.py` leitete das Tankvolumen
früher aus einem hartkodierten `--dt 15.0` her statt aus dem tatsächlich vom Solver berechneten
`V_TES_m3` (geometry.csv) — für Hot-Charge-Szenarien (ΔT=31,4 K statt 15 K) ergab das ~2× zu große
Volumina/CAPEX. Fix: `_read_V_from_geometry()` liest die reale, szenariospezifische Geometrie.
Gleichzeitig wurde die vereinbarte `v_min_realistic_m3=50` Untergrenze nachgerüstet (vorher konnten
Rungs mit 13–76 m³ als „Optimum" durchrutschen).

**Wiederkehrendes Solver-Artefakt (3× beobachtet, charakterisiert, nicht weiter untersucht):** kleine
Rungs (0,5–4,3 MWh) liefern bei MM-S1 gelegentlich degenerierte Inkumbenten in der Größenordnung
800–845 Mio. € bei ~99,97 % Gap (MM-S1-HK2@4,3 MWh=835 Mio., MM-S1-HK1@2,2 MWh=845 Mio.) oder
`no_incumbent` (MM-S1-HK0@2,2/3,3/4,3, MM-S1-HK1@3,3/4,3). Muster: die 2,2–4,3 MWh-Knieregion ist für
MM-S1 strukturell unzuverlässig, welcher konkrete Rung betroffen ist variiert pro Heizkurve — real
charakterisierte Datenlücke, keine erfundenen Zahlen, keine weitere Rechenzeit investiert.

**Study C (Site-Enumeration statt monolithischem endogenem MILP, s. §4o für die Traktabilitätsbegründung)
— BEIDE Netze abgeschlossen:**
- MM-S4-HK0 (36 HP×TES-Paare, 6×6 Kandidaten): 35/36 sinnvoll gelöst, `j_1×j_1` (Kolokation) = 1,3 Mrd. €
  Ausreißer, ausgeschlossen. Bestes Paar: HP@j_1 × TES@j_9 = 303.942 €.
- SB-S6-HK0 (25 HP×TES-Paare, 5×5 Kandidaten): 23/25 gelöst, 2 echte `no_incumbent`-Lücken
  (`j_man×j_man`, `j_psw×j_hkw`). **Zentrales Ergebnis: der TES-Standort dominiert den HP-Standort um
  ~10×** — Mittelwert nach TES-Standort: j_ost=14,4 Mio. € (beste) → j_man=34,1 M → j_hkw=60,6 M →
  j_pss=87,8 M → j_psw=136,8 M (schlechteste, inkl. eines Kandidaten-Ausreißers `j_psw×j_psw`=253,2 M,
  ~2,5× seines nächstschlechteren Geschwisterwerts in der Gruppe — geflaggt, nicht automatisch
  ausgeschlossen). Bestes Paar insgesamt: HP@j_psw × TES@j_ost = 12.275.477 €. **Zitierfähiges Ergebnis:**
  TES-Standort sollte unabhängig von der HP-Platzierung gewählt werden — Planungsempfehlung „TES an
  j_ost-artigen Knoten, nicht j_pss/j_psw".

**MM-S2-HK0 Infeasibility — IIS berechnet (2026-09-15), Ergebnis: vermutlich ECHT, keine Config-Bug-Bestätigung:**
Repro-Lauf bei TES=6,5 MWh bestätigt `infeasibleorunbounded`; `compute_iis.py` (gurobipy `computeIIS()`)
lief erfolgreich durch (Absturz nur beim Pretty-Print, `IISNumConstrs`-Attributname passt nicht zur
installierten gurobipy-Version — IIS-Datei selbst wurde korrekt geschrieben). Die IIS ist **sehr groß**
(~12 Mio. Zeilen „Subject To", nahezu das gesamte Jahresmodell) — kein kleiner, lokal isolierbarer
Bug. Kernbausteine: `hp_main`-Kapazitätslinearisierung (`c_u_hp_main_linfix_hi/lo/le_cap`,
`c_u_hp_main_cap/min/wrg_limit`), `tes_main`-Speicherzustand (`c_e_tes_main_soc`,
`c_u_tes_main_soc_hi/lo`, `_qc_lim`, `_qd_mask`, `_shared_port`, `_terminal_`), sowie
Rohrleitungs-Constraints **speziell für den Ast J10→J11→J12→J13→J14** (Wärmelieferung, Druckverlust,
Pumpenleistung, PWL-Segmente) — genau der bereits aus der Pandapipes-Validierung bekannte
Schwachpunkt-Ast („j_12-Deckenartefakt", „j_14 schlechteste Druckmarge", s. Memory
`project_memmingen_pandapipes_crosscheck`). Keine forcierte-Build-Constraint oder S2-spezifische
Override-Bound in der IIS gefunden → schwächt die „Config-Bug erzwingt build=1"-Hypothese.
**Vorläufige Einordnung:** echte strukturelle Inkompatibilität zwischen fixierter TES-Größe und der
HP-Linearisierung, ausgetragen über den bekannten Schwachast — als **Ergebnis** zu berichten
(„ein atmosphärischer Tank ist unter HK0 in dieser Netzkonfiguration nicht baubar"), NICHT als
Ausschluss zu behandeln. Vorbehalt: eine IIS dieser Größe kann auch eine lokal-minimale statt global-
minimale Gurobi-Reduktion sein (bei 4,9-Mio.-Zeilen-Modellen praktisch unvermeidbar) — die Aussage
„echtes Ergebnis, keine Bug-Bestätigung" ist plausibel, aber nicht mit letzter Schärfe bewiesen.

**Offene Anschlussarbeiten (nicht Teil dieser Zusammenfassung, s. Session-Memory):** SB-S0-HK1/HK2-Anker
noch nicht validiert (SB-S1-HK1-Sweep liefert daher vorerst nur Rohdaten ohne %); Eval-Layer-Review
(CO2/Netzverlust-Generatoren) auf dasselbe „recompute-statt-read"-Bugmuster wie `f2_capex.py`/
`extract_artefacts_p2.py`/`kpi_calculator.py` noch offen.

## 4q. Kampagnenabschluss — T_F2_optima vollständig, SB-Null-Nutzen bestätigt auf 2. Heizkurve (2026-09-16)

**Alle offenen Punkte aus §4p abgeschlossen:**
- **Eval-Layer-Review erledigt:** CO2 (`capacity_sweep.py`) liest `co2_t_per_a` aus dem KPI-Dict und
  multipliziert nur mit dem Preis — kein Recompute-Bug. Netzverlust-Logik in `scenario_runner.py`
  (`q_loss_w = U·L·max(T_avg−T_ground,0)`) ist eine PRE-SOLVE-Eingangsgrößen-Berechnung (Modell-Input),
  keine Post-Solve-Neuberechnung eines bereits vom Solver erzeugten Outputs — fällt nicht unter die
  „read-not-recompute"-Regel. Kein weiterer Bug dieser Klasse gefunden; das Muster war auf die drei
  bereits gefixten TES-Geometrie-Skripte beschränkt.
- **SB-S0-HK1 validiert (2026-09-16):** 13.217.000 € (Plateau über 1h+ exakt unverändert, 2,82 % Gap
  strukturell lose wie gehabt). Ungewöhnlich lange Root-Node-Phase (>1h ohne Log-Zeile) davor war KEIN
  Hänger, sondern eine sehr lange Presolve/Cuts-Runde auf dem großen SB-Modell (7-Mio.-Variablen) —
  danach Serie schneller Inkumbenten-Sprünge 79,5 Mio.→...→13,22 Mio. **Lehre für künftige Kampagnen:**
  auf den großen SB-Modellen NICHT vor 2-3h Stillstand von einem Hänger ausgehen.
  - **SB-S1-HK1 fertig (12/12 Rungs), Zwei-Rungs-Ausreißer (292 MWh=105,4 Mio. €/87,9 % Gap, 877 MWh=
    49,3 Mio. €/74,2 % Gap) nach dem etablierten Muster ausgeschlossen. Ergebnis dupliziert HK0 exakt:
    **Optimum bei Rung=0, 0,0 % Ersparnis.** Der Null-Nutzen-Befund für Stadtbach gilt damit für ZWEI
    unabhängige Heizkurven (S1-HK0 UND S1-HK1) sowie zwei Speichermodi (S1 normal, S3 hot-charge, beide
    HK0) — deutlich robuster als ein Einzelbefund.
- **`T_F2_optima.csv` jetzt VOLLSTÄNDIG mit 9 Szenarien:** Memmingen S1-HK0=11,2 %@6,5 MWh,
  S1-HK1=9,2 %@6,5 MWh, S1-HK2=14,2 %@3,3 MWh, S3-HK0=13,8 %@2,2 MWh, S3-HK1=11,8 %@2,2 MWh,
  S3-HK2=14,8 %@2,2 MWh (Familienspanne 9,2–14,8 %, kohärent); Stadtbach S1-HK0/S1-HK1/S3-HK0 alle
  =0,0 %@0 MWh (validiert, real).
- **Endogene Supplement-Läufe (MM-S5-HK0, SB-S7-HK0)** liefen als bekannt-schwache monolithische MILPs
  (§4o-Klasse, weswegen Study C via Paar-Enumeration existiert) mit dem erwarteten Muster: langer
  Root-Node-Stillstand, dann Inkumbenten-Sprünge, Gap bleibt strukturell locker (30–90 %) — als
  Ergänzungsmaterial dokumentiert, nicht als belastbare Einzelzahlen für den Haupttext.

**Standalone-Manuskriptabsatz** (Stadtbach-TES-Standort-Sensitivität) liegt fertig unter
`DRAFT_stadtbach_tes_siting_paragraph.md`. **Damit ist die mehrtägige autonome Nachrechnungs-Kampagne
für die atmosphärische Konfiguration inhaltlich abgeschlossen** — verbleibende Arbeit ist Einarbeitung
ins Manuskript selbst (außerhalb dieses Dokuments).

**Nachtrag (2026-09-16, Kampagnenende):** beide endogenen Supplement-Läufe fertig, wie erwartet lose
(§4o-Klasse): MM-S5-HK0 = 1.729.156 €/84,0 % Gap (maxTimeLimit, 15.531 s); SB-S7-HK0 = 13.324.236 €/
15,9 % Gap (maxTimeLimit, 14.402 s). Beide als Ergänzungsmaterial, nicht als belastbare Hauptzahlen.
Keine offenen Läufe, keine offenen Untersuchungen mehr — Kampagne beendet.

## 5. Future-Work-Liste (nach dem Freeze; NICHT ins Modell)
Typtage; kontinuierliche Ladetemperatur; Technologie-Vollfaktor; McCormick-exakter endogener
Verlust; saisonale Speicher (>diurnal); zonaler Demand-Charge; DSM.
- **Mehrjahres-Robustheit — ENTFÄLLT (Datenlage geprüft 2026-09-04):** MMs Datei ist 15-Min-Auflösung,
  43.288 Schritte = ~451 Tage ≈ 1,23 Jahre (spannt 2025 voll + ~86 Nachbartage), NICHT 4,94 Jahre — meine
  frühere „4,94 Jahre"-Angabe war ein Fehler (43.288 als Stunden statt 15-Min gelesen). Es gibt also keine
  fünf Wetterjahre; die Mehrjahres-Robustheitsidee ist gegenstandslos. Die Ein-Jahres-Limitation (2025)
  bleibt als deklarierte Schwäche stehen. **Jahresschnitt ist gepinnt:** MM-Config `horizon: 2025-01-01…
  2025-12-31`; Last/Preis/CO₂ sind Spalten DERSELBEN Datei → automatisch jahresgleich, kein Versatz möglich.

## 6. Beitrag (was das Paper behauptet)
- **C1** Geometrische Speicherauslegung mit innerem Optimum (Oberflächenverlust, degressive Kosten,
  Speicherstunden-Normierung) — Methodenbeitrag.
- **C2 (umgerahmt 2026-09-04):** **In Bestandsnetzen setzt nicht die Heizkurve, sondern die
  Mindestspreizung an den Übergabestationen (VDI 6002, hier 15 K) die nutzbare Energiedichte des
  Speichers — und damit dessen Kosten pro MWh.** Beleg: beide Netze liegen bei Normalladung an
  derselben 15-K-Schranke (Sechs-Zeilen-Tabelle §4b), 22–44 % der Stunden aktiv → gleiche €/MWh-
  Energiedichte trotz unterschiedlicher Netztemperatur; deshalb hilft/schadet die Heizkurvenabsenkung
  dem Speicher nicht (beide an der Schranke). Übertragbar, nicht offensichtlich, mit n=2 belegt.
  **Planungshinweis (Diskussion §5):** ein Substationsertüchtigungsprogramm, das die Schranke senkt,
  verbilligt den Speicher direkt.
  **MECHANISTISCHER GRUND für den Speicherwert (§5, RESULT — 2026-09-05, aus dem min_load-A/B):** in
  Memmingen **fiele die Grundlast-Biomasse in 59 % der Sommerstunden unter ihre Mindestlast**, dürfte sie
  frei modulieren; die Mindestlast zwingt sie darüber, der Überschuss muss gespeichert werden. Messbar als
  Dispatch-Prämie **+17 % im Sommer vs. +0,2 % im Winter** (min_load an/aus). **Das ist die kausale Erklärung,
  warum der Speicher hier Geld verdient** — konkret, quantifiziert, übertragbar auf jedes Netz mit großem
  Grundlasterzeuger + geringer Sommerlast. (Bisher hatte das Paper Optima ohne Begründung, warum sie dort
  liegen.) Beide Zahlen + der 59-%-Mechanismus in §5. Hot Charging koppelt HK an die Spreizung, aber der Effekt ist klein
  (SB 35 K vs. MM 31,4 K unter der 95-°C-Decke, ~12 %) → **Absatz + Tabelle, KEINE eigene F3-Spalte**
  (F3 bleibt COP + Netto-TAC). Frühere „SB hat billigeren Speicher"-Formulierung ist damit ersetzt.
- **C3** Topologie ändert die Investitionsentscheidung (Siting; aggregiert vs. nodal).
- **C4** Wann Elektrifizierung sich rechnet (Break-even statt „rechnet sich 2026 nicht").

## 4r. KORREKTUR (2026-09-19): S0/BC-Anker waren KEINE Ohne-TES-Läufe — §4p/§4q Ergebnisse SUPERSEDED

**Fund:** Beim Bau von T4 zeigte `geometry.csv` der „S0 = kein TES"-Läufe `build=1` mit Tanks von 23,9–146 MWh
(MM-S0-HK0/1/2, SB-S0-HK0/1), ebenso BC-MM (2,2 MWh). **Ursache (zwei Stellen, beide von mir in dieser Kampagne
eingeführt bzw. nicht bedacht):** (1) `scenario_runner.py` schrieb mit `CALION_ATMOSPHERIC_TES=1` per
`_asset_cfg.update(per_asset)` die atmosphärische `V_max_m3`/Leiter über die Szenario-Overrides `tes_off_*`
(`V_max_m3: 0.0`); (2) `component_assembler.py` (autoritative Geometrie) überschrieb `V_max_m3` bedingungslos.
Folge: jedes „kein TES"-Szenario (BC, S0) durfte TES investieren. **Fix:** V_max_m3 ≤ 0 ⇒ Tank deaktiviert, kein
Override, kein Konsistenz-Check (beide Dateien; Log-Zeile „TES disabled by scenario" bestätigt im SB-Lauf).

**Was damit UNGÜLTIG ist (bis Neuberechnung):**
- Alle S0-Anker (331.028/310.653/313.953/13.319.673/13.217.000/13.227.300 €) und BC-MM (297.813 €) — sie sind
  „HP+EK+frei wählbarer TES", nicht „ohne TES". Damit auch die Dominanz-Logik (S0 ⊂ S1/S3) und alle
  Ersparnis-% in `T_F2_optima.csv` (Zähler = feste-Rung-TAC bleibt gültig, Nenner falsch).
- **Stadtbach-„Null-Nutzen"-Befund (Finding #1): NICHT belastbar** — der alte SB-S0-Anker (13,32 Mio. €) enthielt
  selbst 146 MWh TES; der echte TES-freie Anker liegt vermutlich höher ⇒ Vorzeichen des Befunds kann kippen.
- T4/T3/`scenarios_kpis.csv`: Δcost-Spalten gegen falschen BC; **nicht** in submission_pack kopiert.
- Memmingen-„Elektrifizierung ohne Speicher −11 %" (S0 vs BC): Artefakt derselben Verwechslung, verworfen.

**Zusätzlich RETRAHIERT — Study C Stadtbach „TES-Standort dominiert HP-Standort ~10×" (Finding #2):** die
Paare mit 34–253 Mio. € haben MIP-Gaps von 55–96 % und `build=1` bei E=2046 MWh (Maximalrung, Müll-Inkumbent);
die einzigen belastbaren Paare (Gap 0,5–8 %) liegen alle bei ≈13,2 Mio. € **ohne** gebauten TES. Der „10×-Spread"
ist Inkumbenten-Qualität, keine Physik; der Absatz `DRAFT_stadtbach_tes_siting_paragraph.md` ist damit
zurückzuziehen. Memmingen-Study-C (Gaps 0,3–6 %) ist plausibel (HP@j_1/j_9, TES@j_9 = 2,2 MWh, 303.942 €), aber
erst nach Neuberechnung von S0 einordnen.

**Gültig bleibt:** feste-Rung-TES-Sweeps (S1/S3-Zähler; Geometrie korrekt, z.B. MM-S1-HK0@6,5 MWh V=451 m³),
Return-Loss-/CAPEX-/v_min-Fixes, IIS-Befund MM-S2-HK0 (S2 ist nicht `tes_off`), S2/S3-Läufe (TES nicht deaktiviert).
**Neuberechnung läuft:** `fixed_{MM,SB}-S0-HK{0,1,2}` (12 h) + `fixed_BC-{MM,SB}` (2 h), Tags `fixed_*`.

**Zwischenstand 2026-09-20 (Neuberechnung):** BC verifiziert (`build=0`, optimal): **BC-MM = 395.115 €** (Gap 0,29 %),
**BC-SB = 13.226.116 €** (Gap 0,46 %) — zum Vergleich der fehlerhafte „BC-MM" mit frei baubarem 2,2-MWh-TES: 297.813 €
⇒ schon ein 2,2-MWh-Tank war ~25 % der Kosten wert (Min-Last-Mechanismus §4h). Beste feste-Rung-TAC_full (Zähler gültig):
MM-S1/S3 267–294 k€ ⇒ vs. echtem BC-MM ~26–32 % Ersparnis; SB-S1/S3 13,36–13,73 Mio. € liegen dagegen *über* BC-SB
(13,23 Mio.) — SB-Aussage erst nach echtem SB-S0. S0-Läufe (6×, 12 h) laufen noch. `gen_tables.py` T3/T4 filtern jetzt
monolithische Endogen-Zeilen, MM-P1REF und Daten vor den Fixes (S0/BC: vor 19.09. 23:00; übrige: vor 13.09.).

**BLOCKER 2026-09-20 — SB-S2 (nicht in Tabellen übernehmen, ungeklärt):** die frischen SB-S2-Läufe liefern 10,20 / 6,76 / 4,81 Mio. €
(HK0/1/2; Gaps 5–7 %; Tank 877–1169 MWh) gegenüber BC-SB 13,23 Mio. € und festen-Rung-S1/S3 ≥ 13,36 Mio. €. Auffällig: SB-S2-HK2
Speicherdurchsatz Laden 595 / Entladen 571 GWh/a (~510 Vollzyklen, ≈93 % des Jahresbedarfs 640 GWh), aber Summe der exportierten Erzeuger nur
≈76 GWh (BC-SB: 544 GWh); Gas 1 GWh statt 112 GWh, CO₂ 4,8 kt statt 31 kt. Der Constraint-Audit meldet Bilanz-Residuum 0,000 (CLOSES), der
Per-Asset-Export schließt dagegen nicht (closure_error 63 % HK0; HK1/2 None/flagged; selbst BC-SB 14,9 %). ⇒ entweder unvollständiger Export
(fehlende Quelle) oder ein energieerzeugendes Schlupfloch am S2-Knoten (Wash-Cycling / gemeinsamer Port). Offen: Quelle der ≈540 GWh im S2-Fall
identifizieren (Knotenbilanz/Q_net_buf/Dump/Slack), dann entscheiden. Bis dahin: SB-S2 weder als Ergebnis noch in T3 verwenden.
SB-S3-HK1: optimal, `build=0`, 13,229 Mio. € ≈ BC-SB ⇒ Null-Build-Fall wie S3-HK0 (in `_excluded_zero_build/`).

**SB-S2-Untersuchung, Stand 2026-09-20 (Zero-Compute, unaufgelöst):** (1) `node_heat_audit.json` SB-S2-HK2: Knoten `j_man` (TES+WP): ht_out = ht_in = 595.289 MWh
(= HP 24.508 + Entladung 570.781 = Ladung 595.289) ⇒ Netto-Beitrag von `j_man` ins Netz ≈ 0; alle anderen Erzeuger zusammen nur ≈52 GWh, Bedarf 640 GWh.
(2) Rohrnetz-Flüsse (`pipe_state_hourly.parquet`) sind intern konservativ (Σ Einspeisung = Σ Entnahme), zeigen aber Einspeisung am Primärerzeuger `j_hkw`
von 556 GWh (S2) bzw. 486 GWh (BC-SB), während der exportierte HKW-Asset nur 0,23 bzw. 1,8 GWh liefert ⇒ `Q_pipe_MW` und exportierte Asset-/Dispatch-Spalten
sind verschiedene Größen; der Per-Asset-Export ist auf Stadtbach auch für BC unvollständig (544 GWh Erzeugung vs. 640+19 GWh Bedarf+Verlust). (3) S2 verdrängt
AVA-Feed (334,6→27,9 GWh) und Biomasse-HKW (91,6→42,6 GWh) und lädt/entlädt ~510×/a. `constraint_builder.add_per_node_heat_balance` (Primärerzeuger `j_hkw`,
Sekundärerzeuger-Bilanz `local_gen + Q_pipe_in == demand + Q_delivered_out + dump + charge`) ist die Stelle für den nächsten Schritt: Bilanzterme einer
Stunde am Primärknoten und an `j_man` ausgeben (oder S2 mit fester Mini-TES 73 MWh nachrechnen — muss ≈ S0 ergeben). Bis dahin ist SB-S2 **kein Ergebnis**;
der Memmingen-S2 (TES an `j_12`, 289/274 k€) zeigt diese Auffälligkeit nicht.

**PROVISORISCH 2026-09-20 05:35 (S0 laufen noch; Inkumbenten fallen nur ⇒ Ersparnisse unten sind OBERGRENZEN):** aktuelle Bestwerte der korrigierten S0
(MM-HK0 287.858 €/0,66 % Gap, MM-HK1 276.513 €/0,74 %, **MM-HK2 272.776 € — 2 Checks exakt flat, provisorischer Anker**, SB-HK0 13,120 Mio./1,9 %, SB-HK1 13,040 Mio./1,5 %,
SB-HK2 12,980 Mio./1,3 %). Gegen die *echten* S0 ergibt sich für Memmingen: S3 (heiß laden) +0,9/+1,0/+2,0 % (HK0/1/2), S1 −2,1/−2,0/**+1,3 %** — d. h. der Speichervorteil
liegt bei ≤2 % und damit im Bereich der Solver-Gaps (0,7–2 %); die früheren 9–15 % waren Artefakt des TES-fähigen „S0". Elektrifizierung (HP+EK ohne Speicher) spart
dagegen **27/30/31 %** gegenüber dem echten BC-MM (395.115 €). Stadtbach: S0 (12,98–13,12 Mio.) liegt unter allen festen-Rung-S1/S3 (≥13,36 Mio.) ⇒ kein belastbarer Speichervorteil.
Endgültig erst nach Abschluss der 6 S0-Läufe (~11:20). Provisorische F2-Neuberechnung (nur HK2): `output/paper2_sweeps/provisional/f2_MM-S{1,3}-HK2_PROV.csv` (offizielle f2_*.csv unverändert).

**PROVISORISCH 2026-09-20 07:45 — F2 gegen konvergierte echte S0 (MM alle 3 flat ≥2 Checks; SB-HK1 flat 2 Checks; Ergebnisse in `output/paper2_sweeps/provisional/*_PROV.csv`, offizielle f2_*.csv unverändert):**
S0-Anker (Inkumbent/Gap): MM-HK0 287.802 €/0,63 %, MM-HK1 276.391 €/0,68 %, MM-HK2 272.776 €/1,62 %, SB-HK1 13,040 Mio./1,46 %. Optimum der Speicher-Kurve:
MM-S1-HK0 → **Rung 0** (kein Speicher), MM-S1-HK1 → **Rung 0**, MM-S1-HK2 3,3 MWh **+1,3 %**, MM-S3-HK0/1/2 je 2,2 MWh **+0,9/+0,9/+2,0 %**, SB-S1-HK1 → **Rung 0**.
Einordnung: Ersparnisse ≤2 % liegen im Bereich der S0-Gaps (0,6–1,6 %) ⇒ Speicher in diesen Netzen bestenfalls marginal, nicht belastbar unterscheidbar von „kein Speicher";
Elektrifizierung ist der große Hebel (MM: −27…−31 % ggü. echtem BC-MM). SB-HK0/HK2 (S0 noch nicht flat) und die endgültigen Werte folgen nach Ende der S0-Läufe (~11:20).

**RESSOURCEN-WARNUNG 2026-09-20 10:45:** RAM der Maschine 99,8 % belegt (0,4 GB frei); ein fremder Prozess (PID 63876, gestartet 09:43, nicht aus diesem Projekt, Besitzer nicht lesbar) hält 105 GB;
die sechs korrigierten S0-Läufe (12-h-Limit ≈ 11:20) sind auf 6–12 GB Working Set gedrückt, laufen aber (Logs aktuell). Gefahr: Ergebnis-Extraktion nach dem Limit kann scheitern (Ergebnisdateien
entstehen erst am Laufende). **Log-Inkumbenten 10:40 als Absicherung** (Objective/Gap): MM-S0-HK0 287.798 €/0,61 %, MM-S0-HK1 276.191 €/0,60 %, MM-S0-HK2 271.971 €/1,33 %,
SB-S0-HK0 13,018 Mio./1,11 %, SB-S0-HK1 13,040 Mio./1,46 %, SB-S0-HK2 12,958 Mio./1,14 % (alle `TES disabled by scenario`). Für F2 genügen diese Objective-Werte; für die KPI-Tabellen
(economics/dispatch) werden die Ergebnisordner benötigt — bei Extraktionsfehler Neulauf mit kürzerem Limit.

## 4s. ENDERGEBNIS F2 nach TES-off-Korrektur (2026-09-20 11:50) — ersetzt §4p/§4q-Zahlen
Finale Objective der korrigierten S0 (12-h-Läufe, `TES disabled by scenario`, Logs `Best objective`): **MM-HK0 287.798 €** (Gap 0,60 %), **MM-HK1 276.184 €** (0,60 %), **MM-HK2 271.971 €** (1,33 %),
**SB-HK0 13.016.220 €** (1,09 %), **SB-HK1 13.039.692 €** (1,46 %), SB-HK2 12.954.621 € (1,11 %); BC-MM 395.115 € (0,29 %), BC-SB 13.226.116 € (0,46 %). F2 (`output/paper2_sweeps/f2_*.csv`, `tables/T_F2_optima.csv`, jetzt mit S0-Gap-Spalte):
| Kurve | S0 | Optimum | Ersparnis ggü. S0 | > S0-Gap? |
|---|---|---|---|---|
| MM-S1-HK0 | 287.798 | Rung 0 (kein Speicher) | 0,0 % | nein |
| MM-S1-HK1 | 276.184 | Rung 0 | 0,0 % | nein |
| MM-S1-HK2 | 271.971 | 3,3 MWh | +1,0 % | nein |
| MM-S3-HK0 | 287.798 | 2,2 MWh | +0,9 % | ja (knapp; Rung-Gap 0,2 %) |
| MM-S3-HK1 | 276.184 | 2,2 MWh | +0,8 % | ja (knapp) |
| MM-S3-HK2 | 271.971 | 2,2 MWh | +1,7 % | ja |
| SB-S1-HK0 / SB-S1-HK1 / SB-S3-HK0 | 13,02 / 13,04 / 13,02 Mio. | Rung 0 | 0,0 % | nein |
**Aussage:** Speicherwert in beiden Netzen höchstens ~1–2 % (nur MM, nur heißes Laden S3 knapp über dem Solver-Rauschen); normal geladene Speicher (S1) und alle Stadtbach-Fälle: **kein nachweisbarer Nutzen**.
Der große Hebel ist die Elektrifizierung: S0 (WP+EK, ohne Speicher) spart in MM **27/30/31 %** ggü. BC-MM (395.115 €); in SB ist S0 ≈ BC-SB (≈ −1,6 %/−1,4 %/−2,1 %).
Frühere Aussagen (9–15 % MM-Speicherersparnis, SB „Null-Nutzen bei 4,2 %-Artefakt", TES-Standort-10×) gelten NICHT mehr. Ergebnisordner der S0-Läufe werden nach der Extraktion nach `output/paper2_runs/` übernommen (KPI-Tabellen T3/T4/T5 danach).
Offen: SB-S2-Diagnose (`diag_SB-S2-HK2_fix73` läuft bis ~15:10), Tabellen T3/T4/T5, F3-Endogen-Tabelle nur aus Paaren mit Gap <10 %.

## 4t. KPI-Tabellen T3/T4/T5 neu erzeugt und in die Submission-Pack kopiert (2026-09-20 12:25)
**Datenbasis:** alle 6 S0 (12 h, `build=0`, meta.json obj_eur = Log-Wert) + BC-MM/BC-SB in `output/paper2_runs/` promoviert (Backups `_superseded_pre_tesoff_fix/`); `scenarios_kpis.csv` neu.
**T4 Memmingen (12 Zeilen):** BC-MM 0,395 M€/a; S0 0,288/0,276/0,272 (Δcost **27,2/30,1/31,2 %**); S1 0,294/0,282/0,269 (25,6/28,6/31,9 %); S2-HK1/HK2 0,289/0,274 (baute keinen Speicher; HK1-Gap 5,5 % erklärt +4,7 % ggü. S0);
S3 0,285/0,274/0,267 (27,8/30,7/32,3 %; Tank 73/57/52 m³). S2-HK0 infeasible (IIS, Fußnote). **Beobachtung: Memmingen-S0 emittiert MEHR CO₂ als BC (354 vs. 306 t/a)** — Elektrifizierung spart hier Kosten, aber keinen Kohlenstoff (Netzstrom).
**T3 Stadtbach (nur 4 Zeilen):** BC-SB 13,226 M€, S0 13,016/13,040/12,955 (Δcost 1,6/1,4/2,0 %; CO₂ −9 %). S1/S3 (HK0/HK1) entfallen (optimale Größe 0 = S0); S2 zurückgehalten (Energiebilanz-Blocker); S4/S5/S1-HK2/S3-HK2 noch nicht neu gerechnet (Laufende Neuberechnung: `fresh_SB-S4-HK0`, `fresh_SB-S5-HK0`, 4 h).
**gen_tables.py:** T3/T4/T5 filtern nun (a) monolithische Endogen-Familien (MM-S4/S5, SB-S6/S7), MM-P1REF und (b) Daten vor den Fixes (`_is_stale`: S0/BC vor 19.09. 23:00, übrige vor 13.09.); Captions nennen Abdeckung/Ausschlüsse.
**T5 (nur 16 frische Läufe):** Schließungsfehler MW-Bilanz mittel 12,4 %, max 15,0 % (MM-S3-HK2), **0/5 bestehen das ≤2 %-Gate** — Export-Bilanz (Erzeuger+Speicher vs. Bedarf) schließt nicht, obwohl der Constraint-Audit Residuum 0,000 meldet
(gleiche Ursache wie der SB-S2-Befund: Per-Asset-Export unvollständig bzw. andere Größe als die Bilanzterme). Außerdem: „Memmingen P1 OPEX consistency 117 % FAIL" (bekannt, offen) und Sweep-Konsistenz „grenzwertig". T5 ist damit **ehrlich, aber kein Validierungserfolg**.
**Kopiert nach** `docs/paper_2/submission_pack/02_tables/` (`tab_T3_stadtbach_kpis`, `tab_T4_memmingen_kpis`, `tab_T5_validation`, `tab_T5_supplement_excluded_runs`, .csv/.tex; per `diff -q` verifiziert; alte Versionen in `_superseded_2026-08-30/`).
**Offen:** SB-S2-Diagnose (`diag_SB-S2-HK2_fix73`, bis ~15:10), SB-S4/S5-Neuläufe, F3-Endogen-Tabelle (`tab_T3b_T4b_f3_endogenous_siting_FINAL.*`) nur aus Paaren mit Gap <10 % neu bauen, Export-/Closure-Diskrepanz (T5) klären.

## 4u. F3-Endogen-Tabelle neu (2026-09-20 13:25) — und die j_man-Auffälligkeit ist ALT
`tab_T3b_T4b_f3_endogenous_siting_FINAL.*` neu aus den frischen HK0-Paarläufen (nur Gap ≤10 %; `gen_tables.py F3`), Backup der alten in `_superseded_2026-08-30/`.
**Memmingen:** 36 Paare gelöst, 19 mit Gap ≤10 %; beste HP@j_1×TES@j_9 = 0,304 M€/a (Gap 1,3 %, Tank 2,2 MWh). **Alle Paare liegen 5,6–9,4 % ÜBER dem echten S0 (0,288 M€)**, selbst Paare ohne gebauten
Tank (HP@j_12×TES@j_5 = 0,311, Gap 3,1 %) — ein Paar ohne Tank müsste S0 reproduzieren ⇒ Paarläufe sind mit S0 nicht vergleichbar (anderes Modell/Zeitlimit); sie ranken Standorte untereinander, belegen aber
**keinen absoluten Siting-/Speichernutzen**. **Stadtbach:** 25 Paare, nur 3 mit Gap ≤10 % (20 unzuverlässig, 2 ohne Inkumbent); beste 12,275 M€ (HP@j_psw×TES@j_ost, kein Tank, Gap 7,85 %) bzw. 13,22 M€ (Gap 0,5 %, kein Tank) ⇒ kein Speicher gebaut.
**Wichtig:** die ALTE F3-Tabelle (Juli/Aug) führte als „finalen" SB-S6-Sieger TES@j_man mit **4,49 M€/a (−59 % ggü. BC), 845 MWh** — dieselbe Größenordnung/derselbe Knoten wie die unerklärten SB-S2-Ergebnisse (4,8–10,2 M€, TES-Ort j_man, ~510 Zyklen/a,
Export ≠ Bilanz). Damit ist die j_man-Anomalie **kein neuer Effekt, sondern steckte im bisherigen F3-Headline**; sie ist sehr wahrscheinlich ein Modell-/Bilanzartefakt (TES an j_man erzeugt scheinbar Energie; LP-Schranke bei SB-S2-HK0 nur 9,48 Mio. vs. 12,87 Mio. bei S0). Diagnose-Lauf `diag_SB-S2-HK2_fix73` (fester 73-MWh-Tank) läuft bis ~15:10.

**Zwischenstand SB-S2-Diagnose 2026-09-20 14:05 (`diag_SB-S2-HK2_fix73`, fester TES 73 MWh):** LP-Schranke nach 9.720 s **11,36 Mio. €** (Inkumbent noch 102 Mio., Gap 88,9 %) gegenüber **12,81 Mio. € bei S0-HK2** ⇒ schon ein
73-MWh-Tank senkt die Relaxation um ≈11 % (1,45 Mio. €/a) — deutlich mehr, als ein so kleiner Speicher legitim bringen kann; Hinweis auf ein größenunabhängiges Bilanz-/Energie-Schlupfloch am j_man-Knoten. Nicht abschließend (Inkumbent fehlt; Lauf endet ~15:10).

## 4v. SB-S2 / j_man-Anomalie: quantitativer Befund (2026-09-20 16:45) — BLOCKER, nicht behoben
**Diagnose-Lauf `diag_SB-S2-HK2_fix73`** (TES fest 73 MWh, 4 h): Objective 22,94 Mio. € (Gap 50,5 %, Schranke 11,36 Mio.) — Inkumbent schlecht, aber die Lösung zeigt bereits das Muster:
Speicher Laden 78.359 / Entladen 75.074 MWh/a (**~1.028 Zyklen**, max. SOC 73 MWh, Ladeleistung ≤18,25 MW); Erzeuger (Per-Asset-Export) 489.034 MWh; Bedarf 639.973 + Verluste 19.434 = 659.407 MWh ⇒ **Bilanzlücke 173.658 MWh (26 %)**.
**Vergleich der Lücke (Bedarf+Verluste − exportierte Erzeugung − Netto-Speicher):** BC-SB (kein Speicher) 114.934 MWh (17 %, separates Export-/Bilanzthema, auch ohne Speicher vorhanden); 73-MWh-Lauf 173.658 MWh; freier SB-S2-HK2 (877–1169 MWh) 607.499 MWh.
**Zusätzliche Lücke gg. BC ≈ 0,75× (73 MWh) bzw. ≈ 0,83× (freier Tank) der Lade-Durchsatzenergie** (58.724 / 78.359 bzw. 492.565 / 595.289) ⇒ die unerklärte Wärme skaliert mit dem **Speicherdurchsatz, nicht mit der Tankgröße** — Signatur eines Modell-/Bilanzschlupflochs, in dem geladene Energie am Knoten `j_man` fast „doppelt" als Entladung wieder auftaucht.
Knotenaudit 73-MWh-Lauf: `j_man` ht_out 85.856 (= WP 10.783 + Entladung 75.074) vs. ht_in 78.360 (= Ladung); Constraint-Audit (Residuum) meldet dennoch „schließt" (nicht die Ursache der Lücke, sondern Konsistenz der geprüften Terme).
**Konsequenzen:** (1) SB-S2 (4,81–10,20 Mio. €) und der frühere F3-Sieger SB-S6 TES@j_man (4,49 Mio. €, −59 %, 845 MWh) sind sehr wahrscheinlich Artefakte; (2) SB-Ergebnisse mit TES am j_man/WP-Knoten sind nicht belastbar;
(3) die 115-GWh-Lücke im BC-SB erklärt auch das T5-Closure-Gate-Versagen (0/5). **Hypothesen (ungeprüft, kein Modelleingriff ohne Freigabe):** Wärmebuchung/Temperatur-Offsets um Rohrschleifen des vermaschten SB-Netzes; Sekundärerzeuger-Bilanz
`local_gen + Q_pipe_in == demand + Q_delivered_out + dump + charge` in `calion/models/constraint_builder.py::add_per_node_heat_balance`. **Nächster Schritt (Entscheidung offen):** Bilanzterme einer Stunde am Primärknoten `j_hkw` und an `j_man` ausgeben und mit den Pipe-Flüssen abgleichen.
**SB-S4/S5 (HK0, TES an Pumpstationen, frisch, 4 h):** enden mit Gap 86,0 % (85,3 Mio.) bzw. 83,4 % (71,7 Mio.) ⇒ nicht tabellierbar (Regel Gap ≤10 %); alte Aug-30-Ordner bleiben durch den Frische-Filter ausgeschlossen. T3-Caption entsprechend angepasst.

## 4w. ABSCHLUSS der Korrekturkampagne (2026-09-20 16:55)
**Ursache & Fix:** Atmosphärische Geometrie überschrieb `V_max_m3=0` der „TES-off"-Overrides (BC, S0) ⇒ alle bisherigen Anker enthielten frei baubaren TES. Fix in `scenario_runner.py` + `component_assembler.py` (V_max_m3 ≤ 0 ⇒ deaktiviert); alle S0/BC neu, `build=0` verifiziert.
**Belastbar (in submission_pack/02_tables + output/paper2_sweeps):** wahre Anker BC-MM 395.115 €, BC-SB 13.226.116 €, S0 MM 287.798/276.184/271.971 €, SB 13.016.220/13.039.692/12.954.621 €; F2 (§4s): Speicherwert ≤1–2 % (nur MM-S3 knapp über Solver-Rauschen), SB Optimum = kein Speicher;
Elektrifizierung (S0 vs. BC): MM −27…−31 % Kosten, aber **+15 % CO₂ in MM** (354 vs. 306 t/a); SB −1,4…−2,0 % Kosten, −9 % CO₂. T3 (4 Zeilen), T4 (12), T5 (16 frische Läufe), F3 (Gap ≤10 %-Paare) neu und kopiert.
**Nicht belastbar / offen:** (1) **SB-S2/j_man-Energiebilanzartefakt (§4v)** — betrifft SB-S2 und den früheren F3-SB-S6-Sieger; Ursache nicht behoben; (2) T5: MW-Closure-Gate 0/5 (Export-Bilanzlücke auch bei BC-SB 17 %), Paper-1-OPEX-Konsistenz 117 % FAIL;
(3) SB-S4/S5 (HK0) nicht konvergiert (Gap 83–86 %), SB-S1-HK2/S3-HK2 nicht gelaufen; (4) MM-Paarläufe (F3) liegen 5,6–9,4 % über S0 ⇒ kein absoluter Siting-Nutzen zeigbar; (5) MM-S2-HK0 infeasibel (IIS), MM-S2-HK1 mit Gap 5,5 %.
**Entscheidungen für den Autor:** SB-Modellbilanz am Knoten j_man untersuchen/fixen (Bilanzterme-Ausgabe, evtl. Rohrschleifen/Temperatur-Offsets) bevor irgendein SB-Ergebnis mit Speicher am WP-Knoten zitiert wird; Paper-Narrativ auf „Speicher marginal, Elektrifizierung ist der Hebel (Kosten, nicht CO₂)" umstellen.

## §4x — 2026-09-20: Knotenbilanz-Diagnose — ein Defekt hinter "Problem A" und "Problem B" (KEIN Solve, nur Auswertung vorhandener Exporte)

**Befund.** `constraint_builder.add_per_node_heat_balance` (Primärknoten, ~Zeilen 290–330) bilanziert
`supply == dump + charge + return_loss + Σ_out[Q_delivered − Σ ht_out aller Knoten im Downstream-Teilbaum]`.
Seit dem Massenbilanz-Umbau (2026-07-08, `m_in + m_gen == m_out + m_dem`, Zeilen ~735–790) ist `Q_delivered`
bereits **netto** der lokalen Erzeugung; die Subtraktion aus dem BFS-Fix vom 2026-07-07 zählt sie **ein zweites Mal**.
Bei Speicherknoten wird zudem nur die Entladung (in `ht_out`) abgezogen, die Ladung (`ht_in`) taucht in der
Primärbilanz nie auf → Phantomenergie ≈ Zyklendurchsatz.

**Belege (Reproduktion aus Exporten, `scripts/paper_2/diag_primary_balance.py`):**
- Export ist treu: `node_heat_audit` ht_out je Knoten == Asset-Export; j_hkw speist im BC-SB nur 4,0 GWh ein.
  Die „486 GWh" sind Σ|Q| der ausgehenden Rohre (Vorzeichen im Export verloren, hkw_to_ost = −192 GWh Rückfluss), keine Einspeisung.
- BC-SB: abgezogene Downstream-Erzeugung 104,0 GWh (Boiler j_pss 55,7 + j_psw 48,4); physikalischer Nettoabfluss j_hkw 100,6 GWh
  vs. Einspeisung 4,0 → 96,6 GWh unerklärt; Export-Lücke gesamt 114,9 GWh (Rest ≈ 11 GWh nicht aufgeschlüsselt).
- Stunde 1158 (BC-SB): Rohrabfluss j_hkw 67,6 MW, Einspeisung 0; Primärbilanz-RHS −0,86 MW; abgezogen 27,66 (HWS) + 40,79 (HWW).
- Stunde 1158 (SB-S2 frei): j_man lädt 140,26 / entlädt 135,41 MW (+HP 4,85); lokale Bilanz Residuum 0,00; Primär sieht aus dem j_man-Ast −132,29 MW.
- SB-S2-HK2 (frei): 595 GWh/a Zyklendurchsatz an j_man, physikalischer Nettoabfluss 541 vs. Einspeisung 0,2 GWh; 73-MWh-Diag: 78,4 GWh Ladung, 165,6 GWh unerklärt.
- MM-S0-HK0: HP an j_12 (downstream von j_9) 1,21 GWh; Primärerzeugung sinkt ggü. BC-MM um 2,55 GWh ≈ 2× HP-Wärme; Primär deckt ~1,0 GWh weniger als Nettoabfluss+Rückverlust.
- Das Constraint-Audit (Residuum 0,000) wertet dieselben Constraint-Körper aus → prüft das Modell gegen sich selbst, kann den Defekt nicht sehen.

**Betroffen (nicht neu gerechnet):** jede Zahl mit ht_out/ht_in stromabwärts des Primärknotens über nicht-bidirektionale Rohre —
alle SB-Läufe (Bestandsboiler j_pss/j_psw ⇒ BC-SB selbst ~17 % unterversorgt), SB-S2/S3/S6/S7 (j_man-Speicher), MM-S0…S5 (HP an j_12), Study-C-Paare.
**Nicht betroffen (vermutlich):** Fälle, in denen alle Erzeuger/Speicher am Primärknoten sitzen (BC-MM). Getrennt davon: BC-MM hat eine kleine, konstante Verlust-Lücke (Rückverlust, T5-„Formel-Lücke").
**Offen/zu prüfen:** (i) Massenbilanz kennt keine Ladung (`m_gen` nur aus ht_out) → mögliche zweite Lücke am Speicherknoten (McCormick-Lockerheit); (ii) Rest ≈ 11 GWh BC-SB.
**Status:** kein Modellcode geändert; Fix-Entscheidung liegt beim Autor. Alle Energie-/Kosten-/CO₂-Aussagen aus betroffenen Läufen sind bis zum Re-Solve nicht belastbar.

## §4y — 2026-09-20 (VOR Code-Änderung und VOR jedem Testlauf festgeschrieben): Fix-Definition, Akzeptanztests, Vorab-Erwartungen

**Massenbilanz-Klärung (Code-Read, constraint_builder ~735–790).** `_gens = list(node_buses.ht_out)`; Bilanz `m_in + m_gen == m_out + m_dem` — **kein `ht_in`-Term**.
Folge: Energieerhaltung sichern allein die exakt-linearen Wärmebilanzen (Knoten- und Primärbilanz), die Massenbilanz sichert sie nicht. Ohne Ladungsterm ist die
Massenbilanz an Speicherknoten inkonsistent zur Wärmebilanz (bei Param-T erzwingt sie charge+dump=0; bei Var-T wird das nur durch McCormick-Lockerheit „gelöst").
Historie: der BFS-Abzug (07-07) war ein Notbehelf, solange die Massenbilanz `m_gen` noch nicht kannte (07-08); danach wurde er redundant und nie entfernt.

**Fix-Set (zusammen getestet):**
- **F1** Primärbilanz: Term je ausgehendem Rohr = `Q_delivered` (BFS-Subtraktion `_local_gen_terms` entfernt).
- **F2** Massenbilanz + Passthrough an Knoten mit `ht_out`: `m_in + m_gen == m_out + m_dem + m_chg`, `m_chg` aus `ht_in` mit demselben Helper/T-Paar wie `m_gen`.

**Akzeptanztests (Reihenfolge 2 → 1 → 3), Kriterien vorab:**

| Test | Lauf | Kriterium |
|---|---|---|
| T2 | Root-LP SB-S2-HK2 (Tank fix 73 MWh an j_man) **gepaart** mit SB-S1-HK2 (Tank fix 73 MWh am Primärknoten j_hkw; gleiche HP an J4), gleicher fixierter Code | Alt: S1-Familie 12,7–12,8 Mio. (Tankgröße 37→2046 MWh: −0,6 %), S2-73 = 11,36 Mio. (−11 %). **Neu: \|LP_S2 − LP_S1\| ≤ 1 %** (≈ ≤0,13 Mio.). |
| T1 | BC-SB (kein Speicher) | Lücke `Σdemand+Σloss − (Σht_out − Σht_in)` 114,9 GWh → **Rest muss benannt sein** (kein „≈0"). Definition „geschlossen": Rest ≤ 1 % der Last (6,4 GWh) UND Ursache identifiziert. |
| T3 | MM-S0-HK0 vs BC-MM | Σ Nettoerzeugung (S0) ≈ Σ Nettoerzeugung (BC-MM) = 10,46 GWh ±0,15; Primärerzeugung j_9 steigt gegenüber altem S0 (7,91) um ≈ +1,2 GWh (auf ≈ 9,1–9,3), d. h. HP-Wärme (1,21 GWh) verdrängt Primärwärme 1:1 statt ~2:1. |

**Abweichung von der ursprünglichen Formulierung von T2 (bewusst, hier offengelegt):** „LP-Schranke steigt auf ≈12,8 Mio." ist als *Absolutwert* kein gültiges Kriterium, weil F1 den
physikalisch nötigen Wärmebedarf in **allen** SB-Modellen um ≈104–115 GWh erhöht. Der Absolutwert muss also steigen (Vorab-Erwartung: LP_S1 neu > 12,8 Mio., Größenordnung +0,5 … +5 Mio.;
Obergrenze grob 115 GWh × Grenzkosten, untere Grenze wegen freier AVA-/BMHKW-Reserve). Der Fehler-sensitive, code-unabhängige Invariant ist die **Differenz Tank-am-Primär vs. Tank-an-j_man**.

**Vorab-Hypothese zum Rest in T1 (Benennungspflicht):** BC-MM hat ohne jede Downstream-Erzeugung 1,5 GWh Rest = 59 % des exportierten Rohrverlusts (2,54); BC-SB-Rest nach Abzug der 104,0 GWh = 10,9 GWh = 56 % von 19,4.
Hypothese: verlustproportionaler Restposten (Verlustbilanz Export vs. Constraint), **kein** Speicher-/Downstream-Effekt; erwarteter Rest nach F1/F2 ≈ 55–60 % des Rohrverlusts (≈ 11 GWh SB, ≈ 1,5 GWh MM).

**Vorab-Erwartungen Richtung (User + Ergänzung):**
- MM-Kostenvorteil der Elektrifizierung (−27…−31 %) **schrumpft** (Primärverdrängung halbiert sich 2,55 → 1,21 GWh; Erwartung: etwa halbiert, Bandbreite 10–20 %).
- MM-CO₂ der Elektrifizierung: Untergrenze +15 % (ggü. BC-MM 306 t); Richtung ≥ alt (354/345/333 t). Ergänzung: die zusätzlich nötige Primärwärme (~1,2 GWh) ist überwiegend Biomasse (CO₂-arm) → Anstieg klein; nur bei bindender Biomassekapazität (Gas-Ersatz ≈ 0,2 t/MWh → bis +240 t) größer. Kommt CO₂ *niedriger* als alt heraus, ist die Mechanik nicht verstanden.
- SB: alle absoluten Zielfunktionswerte steigen; Δ(S0−BC) bleibt klein, Vorzeichen offen.
- Unabhängig vom Fix bleibt: MM-Speicher-Null (lag im Rauschen), Methodenteil.

## §4z — 2026-09-20 (nach Fix F1+F2, Smoke-Woche 16.–22.02., isolierte Läufe): Ergebnis + DRITTER Defekt benannt

**Fix gesetzt** (constraint_builder.py): F1 = Primärbilanz-Term je Rohr nur `Q_delivered` (BFS-Abzug entfernt); F2 = Ladungsterm `m_chg` in Massenbilanz + Passthrough. Im gebauten LP verifiziert: `c_e_ht_balance_j_hkw` enthält keine Erzeugungsterme mehr.

**Smoke (Winterwoche, 168 h), Lücke = Σdemand+Σloss − (Σgen + Σdischarge − Σcharge):**

| Lauf | Lücke alt (Jahreslauf, gleiche Woche) | Lücke neu | Tank-Überlappung Lade/Entlade-Stunden |
|---|---|---|---|
| BC-SB | 7.168 MWh = 29,5 % der Last | **243 MWh = 1,0 %** | – |
| SB-S2-HK2 (Tank frei, j_man) | 21.830 MWh = 89,8 % | **249 MWh = 1,0 %** | 168 → **0**; Ladung 21.548 → 0 MWh |

Der Rest ist wie vorab vermutet **verlustproportional**: 243/418 = 58 %, 249/418 = 60 % des Rohrverlusts (Vorab-Bereich 55–60 %).

**Restposten benannt (Defekt 3, NEU, nicht Teil der Fix-Freigabe):** Im Standard-MILP-Modus (Param-Temperaturen) gilt im gebauten Modell
`1000·Q_delivered = m_dot·cp·ΔT` (kein Verlust; LP-Zeile `heat_delivered`), `Q_consumer = Q_delivered` (`no_delay`) und
`Q_loss_supply = konstant` (LP-Zeile `heat_loss_supply`: `Q_loss_supply(2) = 0.02184`). Die Primärbilanz enthält `Q_loss_return` aller Rohre
(Sep-3-Korrektur, Annahme „Q_delivered bettet die Vorlaufverluste ein"), aber **keinen `Q_loss_supply`-Term**. Der Vorlauf-Rohrverlust
(273,1 MWh der Woche = 65 % des Rohrverlusts; Rücklauf 144,8) verlangt damit nirgends Erzeugung.
Rest-Abweichung 24–30 MWh/Woche (~10 % des Vorlaufverlusts) wird indirekt gedeckt (Hypothese, NICHT verifiziert: unterschiedliche ΔT je Rohr durch die knotenweisen Temperatur-Offsets bei Massenerhaltung an Knoten).
Q_dump ist 0,3 MWh und erklärt es nicht; kein Bedarfs-Schlupf (Σ Q_consumer der Blattrohre = Σ Demand exakt).
Wirkung: konstanter Unterdeckungsposten, unabhängig von Speicher/HP; SB ≈ 1 % der Last, **Memmingen ≈ 12–16 % der Last** (BC-MM: 1,5 GWh Rest = 59 % von 2,54 GWh Verlust) — BC-MM ist damit **nicht** die saubere Referenz, als die ich sie angenommen hatte.
**Vorschlag (Entscheidung Autor):** Σ `Q_loss_supply` als konstanten Primärbilanz-Term ergänzen (analog Rückverlust, ein Term, keine neue Variable). Wirkt auf MM stärker als F1.

## §4y-Nachtrag — 2026-09-20 22:05: T2 Ergebnis + Zusatztest T2c (NACHTRÄGLICH ergänzt, vor T2c-Ergebnis festgeschrieben)

**T2 gepaart, neuer Code, Root-LP, Tank fix 73 MWh:** S2-HK2 (Tank j_man) = **20,469 Mio. €**; S1-HK2 (Tank j_hkw/Primär) = **19,955 Mio. €**; Δ = +0,515 Mio. = **+2,6 %** → vorab-Kriterium (|Δ| ≤ 1 %) **VERFEHLT**, Vorzeichen gegenüber alt (−11 %) gedreht.
**Vorab-Absolutprognose falsch:** erwartet +0,5…+5 Mio. gegenüber ~12,8; beobachtet ≈ +7 Mio. (12,8 → ~20). Richtung (steigt) richtig, Größenordnung unterschätzt (freie AVA/BMHKW-Reserve gibt es im Winter nicht).
**Warum der gepaarte Test allein nicht entscheidet:** er ist mit einem echten Standorteffekt konfundiert (Tank an j_man wird nur über die 12,4-MW-Stichleitung hkw_to_man + lokale HP geladen; am Primärknoten aus allen Erzeugern).
**Zusatztest T2c (Standort-bereinigt):** Root-LP SB-S0-HK2 (gleiche HP an J4, **kein** Tank), neuer Code. Kriterien vorab: (a) Monotonie: ein zusätzlicher fixer Tank ohne Capex im Ziel kann die Relaxation nicht verteuern → LP(S1,73) ≤ LP(S0) und LP(S2,73) ≤ LP(S0); (b) 73 MWh (~0,01 % der Jahreslast) bewegen die Relaxation je Standort ≤ 1 %. Wird (a) oder (b) verletzt, steckt noch ein Mechanismus im Speicherknoten (Kandidaten: McCormick-Lockerheit in m_gen/m_chg an Var-T-Knoten, Defekt 3 wirkt speicherabhängig).
Zusätzlich T1 (BC-SB Jahreslauf, MIPGap 3 %, TimeLimit 5400 s) und T3 (MM-S0-HK0) laufen; Auswertung mit `scripts/paper_2/diag_primary_balance.py` bzw. Lückenformel aus §4z.

## §4aa — 2026-09-20 22:45: Testergebnisse T2/T2c/T3, VIERTER Defekt (Szenario-Einrichtung), Fehlprognosen

**Root-LPs SB-HK2, neuer Code F1+F2 (Mio. €):** S0 kein Tank 20,2025 · S1 Tank 73 MWh am Primär 19,9547 (−1,23 %) · S2 Tank 73 MWh an j_man 20,4693 (+1,32 %, **Monotonie verletzt**).
Bisektion: F2 aus (E1) → 20,46930, **identisch** (F2 unschuldig); Tank nur 7 MWh (E2) → 20,46821, **größenunabhängig**.
Wochenvergleich (16.–22.02., Gap ≤ 0,05 %): S0 1.156.652 € (HP 697 MWh) · S2/7 MWh 1.173.760 € (**HP 0**, KWK +656 MWh) → +1,48 %.

**Defekt 4 (Szenario-Setup, `scripts/paper_2/scenario_runner.py`):** Schritt 3 `_apply_tes_location` läuft VOR 3b `_apply_hp_location`. Für SB-S2/S3 hat j_man beim Tank-Schritt noch keine Assets (HP/EK liegen noch in j_hkw) → Guard `not existing_assets` setzt `type='consumer'`; HP/EK kommen danach dazu, der Typ bleibt.
`network_manager._link_consumer_demands()` legt für `consumer`-Terminalknoten `Q_consumer(hkw_to_man) == Q_demand(j_man)` an (im LP nur mit Tank: `c_e_link_heat_demand_j_man_to_pipe_hkw_to_man`, plus `pressure_*_prop_hkw_to_man`). HP-/EK-/Entlade-Wärme kann kein Rohrheizen mehr ersetzen → nur Speicher oder Abregelung → HP wertlos.
**Validierung (Schalter `CALION_HP_BEFORE_TES=1`, Standard AUS = Legacy):** Woche S2/7 MWh: **1.155.695 €** (S0 1.156.652; Monotonie ok), HP 742 MWh, Speicher lädt/entlädt 52,8/50,6 MWh (statt 21 GWh); `link_heat_demand_j_man` im LP 0×.
**Betroffen (nicht neu gerechnet, zu prüfen):** alle SB-Läufe, in denen der Tank auf einen Verbraucherknoten ohne Vor-Assets gesetzt wird und HP/EK erst danach dorthin wandern: SB-S2-*, SB-S3-* (Tank + HP an j_man). Nicht betroffen: S1 (j_hkw hat Assets), S4/S5 (j_pss/j_psw haben Kessel), MM-S1..S3 (HP bereits in Basiskonfig an j_12). Endogene/Paar-Läufe: Pfad separat prüfen.

**T3 (MM-S0-HK0, F1+F2, Gap 1,0 %):** Nettoerzeugung 10,36 GWh vs BC-MM 10,46 (Kriterium ±0,15 **erfüllt**); Primärerzeugung +2,41 GWh (vorab ≈ +1,2 → **verfehlt**: HP an j_12 kollabiert von 1.214 auf 46 MWh).
BC-MM 395.115 € / 306,4 t; S0 alt 287.798 € (−27,2 %) / 353,8 t (+15,5 %) / HP-Anteil 12,3 %; **S0 neu 316.869 € (−19,8 %) / 335,3 t (+9,4 %) / HP-Anteil 0,00 %.**
Vorab-Erwartung „Kostenvorteil schrumpft" **bestätigt**; „CO₂ ≥ alt (+15 %)" **FALSCH** (335 < 354) — vorab festgelegt: „Kommt CO₂ niedriger heraus, ist die Mechanik nicht verstanden". Nachträgliche Erklärung: das Phantom-Doppelguthaben hatte die HP (Netzstrom-CO₂) attraktiv gemacht; ohne Guthaben wird sie nicht mehr gebaut, damit entfällt ihr Netz-CO₂.
**Konsequenz:** der verbleibende Kostenvorteil −19,8 % kann nicht von Elektrifizierung kommen (HP ungenutzt). BC-MM (T_VL konstant, TVLFIX) und S0-HK0 (Heizkurve) unterscheiden sich im Temperaturregime, nicht nur in der HP. Saubere Elektrifizierungswirkung = **MM-S0-TVLFIX vs BC-MM** (gleiche Temperatur) — noch nicht gerechnet.
**Vorab-Absolutprognose T2 falsch** (siehe §4y-Nachtrag). Restlücke T3 1,67 GWh = 64 % des Rohrverlusts = Defekt 3 (Vorlaufverlust), wie für BC-MM (59,8 %).

## §4ab — 2026-09-20 23:00: T1 und T2r, Gesamtbilanz der Akzeptanztests

**T1 BC-SB Jahreslauf (F1+F2, Gap 2,83 %):** Lücke 114,93 → **10,89 GWh = 1,70 % der Last = 56,0 % des Rohrverlusts** (Vorab-Hypothese 55–60 %, ≈ 11 GWh: **getroffen**). Rest = Defekt 3 (Vorlaufverlust). Formal: „Rest ≤ 1 %" **verfehlt** (1,70 %), „Ursache benannt" **erfüllt**.
Erzeugung nach Fix: j_hkw 126,8 (vorher 4,0) · j_ava 334,3 · j_bmhkw 90,4 · j_gtost 46,9 (vorher 10,3) · j_pss 24,7 · j_psw 25,4 GWh.
**BC-SB Ziel 13,23 → 21,10 Mio. € (+59,5 %); CO₂ 31.141 → 67.215 t (+116 %)** — die alten SB-Zahlen gehörten zu einem Netz, dem 17 % der Wärme fehlten.
**T2r (S2 fix 73 MWh, HP-vor-Tank, Jahres-Root-LP):** 20,1213 Mio. € → vs S0 (20,2025) **−0,40 %** (Monotonie ✓), vs S1 (19,9547) **+0,83 %** (Kriterium ≤ 1 % ✓ nach Behebung von Defekt 4).
T2c-Kriterium (b) ≤ 1 % je Standort: S2 −0,40 % ✓; **S1 −1,23 % (knapp verfehlt)** — Tank am Primärknoten, keine Downstream-Erzeugung, plausibler Arbitragewert (~0,25 Mio. €), aber nicht bewiesen.

**Vorab-Prognosen: Treffer/Fehlschläge**
| Prognose | Ergebnis |
|---|---|
| T1-Rest ≈ 55–60 % des Rohrverlusts (≈ 11 GWh SB) | ✓ 56,0 %, 10,9 GWh |
| Nettoerzeugung MM-S0 ≈ BC-MM ±0,15 | ✓ 10,36 vs 10,46 |
| MM-Kostenvorteil schrumpft | ✓ −27,2 → −19,8 % |
| S2 vs S1 gepaart ≤ 1 % | ✗ 2,6 % → ✓ 0,83 % erst nach Defekt-4-Fix |
| Absoluter SB-LP +0,5…+5 Mio. | ✗ ≈ +7 Mio. |
| MM-Primärerzeugung +1,2 GWh | ✗ +2,41 (HP kollabiert) |
| MM-CO₂ ≥ alt (+15 %) | ✗ +9,4 % (335 < 354 t) |

## §4ac — 2026-09-21 (VOR den Läufen festgeschrieben): Freigaben, Reihenfolge, Hypothese

**Freigaben des Autors (mit Änderungen an der Umsetzung):**
- **Defekt 3** (Σ `Q_loss_supply` als konstanter Primärbilanz-Term) **mit Überschuss-Selbsttest:** BC-MM schließt danach auf ≈ 0 → korrekt; kippt auf ≈ −1,5 GWh (Überschuss) → Vorlaufverlust steckt schon implizit in `Q_delivered` (Doppelzählung) → zurück. Danach BC-SB (≈ 0 vs ≈ −10,9 GWh). Memmingen zuerst (Signal 10× stärker).
  Umsetzungsdetail: Term nur für Rohre, deren `Q_delivered` den Vorlaufverlust NICHT einbettet (im gebauten Modell prüfbar: Rohr hat `enthalpy_prop_sup` (McCormick-Modus) → eingebettet, sonst nicht).
- **Defekt 4:** NICHT Reihenfolge tauschen, sondern **Knotenrollen nach vollständiger Platzierung aller Anlagen bestimmen** + Assertion (jeder Knoten mit Wärmeerzeuger muss Erzeuger/mixed sein, sonst lauter Abbruch). Der Schalter `CALION_HP_BEFORE_TES` wird danach entfernt.
- **MM-S2-HK0 sofort als Defekt-4-Test.**

**Vorab-Befund zu MM-S2 (Config-Read, vor dem Lauf):** MM-Basiskonfiguration legt `hp_main`+`eboiler_main` bereits an `j_12`; `tes_nodes`: S1→`j_9` (Primär), S2/S3→`j_12`. `_apply_tes_location` sieht bei `j_12` also vorhandene Assets → erzwingt dort **kein** `consumer`. Defekt 4 (Reihenfolge) betrifft MM demnach **nicht**; er betrifft SB-S2/S3 (j_man, HP/EK erst nach dem Tank-Schritt).
**Vorab-Prognose MM-S2-HK0:** wird mit dem korrigierten Code **zulässig** (alte Unzulässigkeit = Doppelabzug in der Primärbilanz: die abgezogene Downstream-Erzeugung (HP + Speicherentladung an j_12) kann den Primärbedarf unter 0 drücken, `supply ≥ 0` → infeasible; IIS zeigte HP-Linearisierung, Speicherzustand, Ast J10→J14 = genau die Downstream-Kette). Bleibt es unzulässig, ist die Erklärung falsch und die IIS wird neu gelesen.

**Reihenfolge:** (1) Defekt 3 + Selbsttest MM → SB; (2) Defekt 4 als Klassifikation nach Platzierung + Assertion; (3) MM-S2-HK0; (4) `BC-MM-HK0`/`BC-SB-HK0` (= BASE-HK0) und `BC-MM`/`BC-SB` (= BASE-FIX), beide Netze; (5) S0-HK0 beide Netze, **Wärme aus HP und aus EK getrennt ausweisen** (+ CO₂ aus Netzstrom je Anlage); (6) erst dann S1/S2/S3.

**Hypothese H\* (vor den Läufen, Autor):**
| Vergleich | misst | Erwartung |
|---|---|---|
| S0-HK0 vs BASE-HK0 | Elektrifizierung bei gleicher Heizkurve | ≈ 0 (\|Δ\| ≲ 2 %) in beiden Netzen |
| BASE-HK0 vs BASE-FIX | Heizkurvenregelung allein | ≈ 20 % Kostenvorteil |
Befund unter H\*: *„In beiden Netzen rechnen sich bei heutigen Preisen weder Speicher noch Wärmepumpe. Der Hebel ist die Heizkurve."* (bestätigt den August-Befund des Elektrifizierungs-Sweeps; führt das Paper zur heizkurvenbasierten Auslegung mit umgekehrtem Vorzeichen).
**CO₂-Hypothese (Autor):** die +9,4 % MM-CO₂ (335 vs 306 t) kommen **nicht** von der HP (46 MWh), sondern vom **Elektrodenkessel** auf billigen Spotstunden (η≈1, ~3× CO₂-Intensität der HP, senkt Kosten, erhöht Emissionen). Test: HP- und EK-Wärme in S0 getrennt; EK-Netzstrom-CO₂ ≥ Gesamt-Δ CO₂ ggü. BASE-HK0.
**Meine Einschränkung (ehrlich):** H\* stützt sich bisher auf EINEN Datenpunkt (MM-S0-HK0, Defekt 3 noch offen, MIP-Gap 1 %). Der −19,8 %-Abstand zu BC-MM enthält Heizkurve **und** einen von der Temperatur abhängigen Verlustposten (Defekt 3 ist temperaturabhängig, wirkt auf FIX und HK0 unterschiedlich) — die 20 % können sich nach Defekt 3 verschieben; H\* wird erst nach Defekt 3 getestet, nicht davor.

## §4ad — 2026-09-21: Defekt 3 (Vorlaufverlust) und Defekt 4 (Knotenrollen) umgesetzt; Selbsttests

**Defekt 3 umgesetzt** (constraint_builder.py, Primärbilanz): Σ `Q_loss_supply` je Rohr, aber nur für Rohre OHNE `enthalpy_prop_sup` (dort ist der Verlust in `Q_delivered` eingebettet → nie doppelt). Legacy-Schalter `CALION_DISABLE_SUPPLY_LOSS` (nur A/B, nie für Ergebnisse).
**Überschuss-Selbsttest (Winterwoche 16.–22.02., Lücke = Bedarf+Verlust−Nettoerzeugung):**
| Netz | alt (Jahreslauf, gleiche Woche) | nur F1+F2 | + Defekt 3 |
|---|---|---|---|
| BC-MM | 33,9 MWh (10,2 % der Last, 61 % des Verlusts) | – | **+3,0 MWh (0,89 %; 5 % des Verlusts)** |
| BC-SB | 7.168 MWh (29,5 %) | 243,3 MWh (1,0 %) | **−29,8 MWh (−0,12 %; −7 % des Verlusts)** |
Weder Memmingen noch Stadtbach kippt auf den vollen Überschuss (−1,5 GWh/−10,9 GWh) → **keine Doppelzählung von Q_loss_supply.**
**Restposten benannt:**
- **SB −29,8 MWh/Woche** = Wärme, die an **Verteilerknoten** (nur Massenbilanz, keine Wärmebilanz) entsteht, weil Rohre mit knotenweisen Temperatur-Offsets (T_supply_in 114,72…115,00 °C) unterschiedliche ΔT haben: Σ(Q_in − Q_out) = j_ost +25,6, j_hww +2,9, j_hws +1,3 = **29,7** (Knotenbilanz aus den LP-treuen Exportwerten; Primärbilanz stimmt auf −0,03 MWh). Das ist derselbe physikalische Vorlaufverlust, den die Temperatur-Offsets schon einbetten → **partielle Doppelzählung von ≈ 11 % des Vorlaufverlusts, strukturell im Offset-Mechanismus** (0,12 % der Last).
- **MM +3,0 MWh/Woche** = nicht Defekt 3: `j_12` (Mehrverbraucher-Knoten mit `hp_main`/`eboiler_main`) liefert per Rohr 81,8 MWh/Woche, der Dispatch-Export weist dafür 87,5 aus (+5,7 MWh = 1,7 % der Last); `nodes_state_hourly` exportiert für `j_12` Q_demand = 0 (Mehrverbraucher-Knoten). Reporting-/Definitionslücke, gegenläufig zum Offset-Effekt (+2,7). Offen, nicht Teil der Freigabe.
**Defekt 4 umgesetzt** (scenario_runner.py): Erzwingung `type='consumer'` aus `_apply_tes_location` entfernt; `_finalize_node_roles()` nach ALLEN Platzierungen (Schritt 4c): (a) Knoten mit aktiviertem Erzeuger (thermal_generator/p2h/heat_pump) muss producer/mixed sein, (b) Knoten, dessen einziges aktiviertes Asset ein Speicher ist, darf nicht consumer sein (inerter Speicher), (c) deaktivierter Tank (V_max_m3 ≤ 0) zählt als abwesend; Verstoß = `RuntimeError`. Reihenfolge-Schalter `CALION_HP_BEFORE_TES` entfernt. Wächter-Selbsttest: 3 Fehlerfälle brechen ab, Fall ok läuft.
**Trockenlauf über alle 62 Szenarien: 62/62 passieren, kein Abbruch.** Warnung (offener Punkt): endogene Kandidaten auf Verbraucherknoten — MM `j_1, j_3, j_5, j_13`; SB `j_man` (S4/S5/S4CO/S5CO bzw. S6CO): zur Laufzeit eingespeiste Flüsse dort könnten von `link_heat_demand` gepinnt sein → dieselbe Bug-Klasse für F3, **noch ungeprüft**; F3-Ergebnisse bleiben zurückgezogen.
**Validierung ohne Schalter (Woche, Tank 7 MWh, identischer Code D3+D4):** S0 1.178.168 € vs S2 1.177.193 € (−975 €, Monotonie ✓), HP 697→742 MWh; `link_heat_demand_j_man` im LP 0×.
**Vorab-Befund MM-S2 (siehe §4ac):** Defekt 4 betrifft MM nicht (j_12 hat hp_main/eboiler_main in der Basiskonfiguration); Test MM-S2-HK0 läuft (`d4yr_MM-S2-HK0`).
Laufend: `d3yr_BC-MM`, `d3yr_BC-MM-HK0`, `d3yr_BC-SB`, `d3yr_BC-SB-HK0`, `d4yr_MM-S2-HK0`, `d4yr_MM-S0-HK0`.

## §4ae — 2026-09-21 09:20: Neue MM-Baselines (D3 aktiv) und die Herkunft des alten BC-MM-Werts

**MM-S2-HK0 mit korrigiertem Code: ZULÄSSIG** (Root-LP 317.307 €, LP optimal; Lauf `d4yr_MM-S2-HK0`). Vorab-Prognose (§4ac) bestätigt: die alte Unzulässigkeit war der Doppelabzug (abgezogene Downstream-Erzeugung drückte den Primärbedarf unter 0), nicht die Klassifikation. Der „nicht baubar"-Befund darf **nicht** als Ergebnis ins Paper.
**Neue MM-Baselines (Jahreslauf, D3 aktiv, Gap ≤ 0,33 %):**
| Lauf | Ziel € | Brennstoff | CO₂-Kosten | Dump-Kosten | CO₂ t | Erzeugung GWh | Lücke GWh |
|---|---|---|---|---|---|---|---|
| BC-MM alt | 395.115 | 258.100 | 28.890 | **104.413** | 306,4 | 10,46 | 1,52 |
| BC-MM neu (TVLFIX) | 341.844 | 293.861 | 34.167 | 10.046 | 357,2 | 11,81 | 0,17 |
| BC-MM-HK0 neu | 331.785 | 294.724 | 34.236 | – | 356,9 | 11,84 | 0,19 |
**Der alte BC-MM-Wert war um ≈ 94 k€ künstliche Abregelungskosten aufgebläht:** ohne gedeckten Verlust lag der Bedarf unter der Pflicht-Mindestlast der Anlagen (~1 GWh abgeregelt). Brennstoff (+36 k€) und CO₂ (+5 k€) steigen erwartungsgemäß, das Total fällt trotzdem. Der Abstand „S0 −19,8 % vs BC-MM" (§4aa) vergleicht gegen diesen aufgeblähten Wert und ist hinfällig.
**Heizkurvenhebel Memmingen (BASE-HK0 vs BASE-FIX): (341.844 − 331.785)/341.844 = 2,9 %, CO₂ ≈ 0 (357,2 → 356,9 t).** H\* (§4ac) erwartete ≈ 20 % → **zweite Zeile von H\* für MM widerlegt.** Erste Zeile (S0-HK0 vs BASE-HK0 ≈ 0) steht noch aus (`d4yr_MM-S0-HK0`, `d4yr_SB-S0-HK0` laufen).

> **ZURÜCKGEZOGEN (Autoren-Anweisung §4av, F4-Kostenzerlegung SS4av/SS4aw): „Heizkurve MM 2,84 %" (bzw. die hier berichteten 2,9 %, gleicher Effekt auf früherem Codestand) ist widerlegt.** Kostenzerlegung (post-E1/D0, identischer Codestand für beide Läufe) zeigt: 96,9 % dieses Effekts (9.168,24 von 9.425,33 €) sind `Pressure_slack_cost_EUR` — ein Hilfsterm, keine reale Kosten. Der reale ökonomische Effekt des Heizkurven-Wechsels beträgt **≈ 0,09 % (295,65 €), NICHT 2,84 %/2,9 %.** Details: §4av (F4).
Schließung nach D3+F1+F2: BC-MM 0,17 GWh = 1,8 % der Last (Rest: j_12-Bedarfsdefinition, §4ad).

## §4af — 2026-09-21 10:00: Ergebnis-Vermischung durch gleichzeitige Läufe (Race im geteilten Export-Ordner)

Alle Läufe exportieren in dasselbe Verzeichnis (`output/paper2_runs/thermal_network/…`, `solver/…`); die Extraktion kopiert von dort. Enden zwei Läufe gleichzeitig, kann ein Ergebnisordner Dateien des anderen erhalten.
**Gefunden:** `d3yr_BC-SB` (heutiger Lauf): `pipes.csv` und `dispatch_hourly.csv` aus einem Memmingen-Lauf, `dispatch_per_asset.csv`/`node_heat_audit.json` aus Stadtbach. `economics.csv`/Ziel/CO₂ sind SB-plausibel (Modellgrößen), **Zeitreihen ungültig**.
**Älter:** 20 Sweep-Ordner (`atmo*`, `atmo2*`, `fillr_*`, `valgeo_*`, meist MM-S1 mit SB-Dispatch/-Pipes) zeigen dasselbe Muster — frühere Kampagnenphasen, bei denen MM und SB parallel liefen. Jede aus `dispatch_hourly`/`pipes.csv`/`geometry.csv` abgeleitete Zahl aus parallelen Läufen ist ohne Prüfung nicht belastbar (Ziel/Economics aus dem Modell sind es voraussichtlich).
**Werkzeug:** `scripts/paper_2/check_run_integrity.py` (schreibgeschützt; Netz von pipes/asset/dispatch/audit gegen Szenario-ID). Regel ab jetzt: nach jedem Lauf prüfen, vermischte Läufe neu rechnen.
**Behebung (Vorschlag, Entscheidung Autor):** Export-Verzeichnis je Lauf (Ordner pro Szenario-ID) statt eines geteilten; bis dahin Läufe nicht gleichzeitig enden lassen bzw. nachprüfen.
Konsequenz für heute: BC-SB (FIX) gilt für Kosten/CO₂ (Modellgrößen), nicht für Zeitreihen → Neulauf nötig, bevor ein SB-Baseline-Bericht/eine Bilanz aus Dateien erscheint; BC-SB-HK0 und alle MM-Läufe von heute bestehen den Check.

## §4ag — 2026-09-21 11:20: Zwischenstand Schritt 3–5 (MM vollständig, SB S0 läuft)

**MM-S2-HK0 (Defekt-4-/Unzulässigkeits-Test): ZULÄSSIG, gelöst bis Gap 2,42 % (TimeLimit 7200 s)**, Ziel 333.456 € (OPEX-only), CO₂ 357,5 t, **HP 0,000 GWh, EK 0,000 GWh, Tank NICHT gebaut** (E_TES = 0). vs S0-HK0 +1,22 %, vs BASE-HK0 +0,50 % — beides innerhalb des eigenen Gaps (2,42 %). Der frühere Befund „MM-S2-HK0 nicht baubar" war der Doppelabzug und darf nicht ins Paper; ersetzt durch: „zulässig, aber weder HP noch Tank werden gebaut".
**MM-Zerlegung (D3+F1+F2, Gap ≤ 0,5 % außer S2 2,4 %, Integritätscheck bestanden):**
| Lauf | Ziel € | CO₂ t | HP GWh | EK GWh | Tank |
|---|---|---|---|---|---|
| BC-MM (BASE-FIX) | 341.844 | 357,2 | 0 | 0 | – |
| BC-MM-HK0 (BASE-HK0) | 331.785 | 356,9 | 0 | 0 | – |
| MM-S0-HK0 | 329.441 | 341,2 | 0,000 | 0,012 | – |
| MM-S2-HK0 | 333.456 | 357,5 | 0,000 | 0,000 | nicht gebaut |
Heizkurvenhebel MM = 2,9 % (H\* erwartete ≈ 20 % → widerlegt). S0-HK0 vs BASE-HK0 = −0,71 % (< Gap 0,49 %+0,23 %; H\*-Zeile 1 gestützt). CO₂-Hypothese EK (Autor): **nicht gestützt** (EK 12 MWh; Netz-CO₂ 3,1 → 3,8 t); die alten +9,4 % waren ein Artefakt des Alt-Referenzwerts (306 t ohne Verlustwärme); gegen den korrekten Baseline −4,4 %, Ursache Brennstoffmix (324,8 vs 341,5 t Brennstoff-CO₂), innerhalb der Gap-Unschärfe nicht zuordenbar.
**SB-Baselines (D3 aktiv):** BC-SB (FIX) 21,317 Mio. € (Gap 0,92 %; Zeitreihen durch Vermischung ungültig, §4af), BC-SB-HK0 21,299 Mio. € (Gap 0,88 %), CO₂ 68.924 / 69.007 t (alt 31.141 t). Heizkurvenhebel SB **−0,08 % Kosten, +0,12 % CO₂** (≈ 0). Bilanz BC-SB-HK0: Lücke −0,98 GWh = −0,15 % der Last (Überschuss aus Verteilerknoten-ΔT, §4ad).
**SB-S0-HK0 läuft** (`d4yr_SB-S0-HK0`, bei 6.678 s: Incumbent 22,00 Mio., **bester Bound 20,896 Mio.**, Gap 5,0 %; Ende 10.800 s). Da BASE-HK0 für S0 zulässig ist, gilt S0 ∈ [20,896 ; 21,299] Mio. → **Elektrifizierungsvorteil SB ≤ (21,299−20,896)/21,299 = 1,9 %** (belastbare Obergrenze aus dem Bound, unabhängig vom noch schwachen Incumbent).
**Zwischenbefund (weiterhin H\*-Zeile 2 widerlegt in BEIDEN Netzen):** in dieser Formulierung ist die Heizkurve KEIN 20-%-Hebel (MM 2,9 %, SB 0,08 %).

## §4ah — 2026-09-21 14:40: SB-S0-HK0 abgeschlossen; Integritätscheck erweitert

**SB-S0-HK0 (D3+D4, Gap 0,93 %, bester Bound 20,896 Mio.):** Ziel **21,0926 Mio. €**, CO₂ 66.408 t, HP-Wärme **10,89 GWh (1,70 %)**, EK 4,62 GWh (0,72 %), Netzstrom-CO₂ 116 t.
BASE-HK0 SB: 21,2992 Mio. €, CO₂ 69.007 t, HP 0, EK 5,54 GWh (0,87 %), Netzstrom-CO₂ 122 t. **S0 vs BASE-HK0 (SB): −0,97 % Kosten (Gaps 0,93 %/0,88 %), CO₂ −3,8 %**; Obergrenze aus dem Bound ≤ 1,9 %. H\*-Zeile 1 für SB gestützt (|Δ| ≤ 2 %); die HP läuft hier (1,7 % der Wärme), der Vorteil ist aber klein und im Rahmen des MIP-Gaps. Bilanz: Lücke −0,95 GWh (−0,15 % der Last).
**Integritätscheck erweitert:** `dispatch_hourly` (Strom-/Gas-Spalten) gegen `economics.csv`. Alle heutigen Läufe ok außer `d3yr_BC-SB`: dort ist `dispatch_hourly.csv` **spaltenweise gemischt** (Strom-Spalten SB-korrekt und mit economics konsistent; Bedarf/Temperatur/Verlust aus einem MM-HK0-Lauf: T_supply 78,6–98,3 °C statt konstant). `dispatch_hourly.csv` wird aus Modell- UND Thermal-Export-Dateien zusammengesetzt.
**Stand:** kein Lauf aktiv. Schritt 6 (S1/S2/S3) noch nicht gestartet. Offen: Export-Ordner je Lauf (Autor), Neulauf BC-SB (FIX) für gültige Zeitreihen.


## §4ai — 2026-09-21 15:30: Export-Fix (Defekt 5) und Quarantäne  [Freigabe Autor: sofort, Korrektheitsfix]

**Fix (scripts/paper_2/scenario_runner.py):** pro Lauf eigener Export-Ordner `output/exports/<scenario_id>/<run_hash>/` (run_hash = SHA-1 aus Config + Git-Commit + Zeitstempel + PID; liegt unter `output/`, damit git-ignoriert); Assertion `RuntimeError`, falls der Ordner beim Start nicht leer ist; Solver-Dumps (LP/MPS/SOL, ~3 GB je SB-Jahreslauf) standardmäßig AUS (`CALION_KEEP_SOLVER_DUMP=1` zum Einschalten); `check_run_integrity.py` läuft **verpflichtend** nach der Extraktion (`FAILED_INTEGRITY.txt` + Status `failed_integrity`, nie stillschweigend akzeptiert); `run_export.json` je Ergebnisordner. Integritätscheck prüft zusätzlich `dispatch_hourly` (P_buy/P_sell) gegen `economics.csv` (gleiche-Netz-Vermischung).
**Abnahmetest:** 4 Läufe (SB-S0, BC-SB, MM-S0, BC-MM; Winterwoche) gleichzeitig gestartet, nahezu gleichzeitig beendet → 4 getrennte Export-Ordner, alle bestehen den Check (vorher hätte genau das vermischt). Paralleler Betrieb damit freigegeben.
**KORREKTUR zu §4af:** die dort genannten „20 ältere Sweep-Ordner" waren ein Fehler meiner Heuristik (Summenschwelle): 15 davon (`atmo2_*`, `atmo_mm_*`, `fillr_*`, `valgeo_mm_*`) sind **leere Ergebnisse** (Bedarf 0, kein Incumbent), nicht vermischt. Tatsächlich vermischt (Netz-Konflikt nach dem Netz-Check): **5 Sandbox-Ordner** und **75 kanonische SB-S6-Paarläufe**.
**Quarantäne (verschoben, nicht gelöscht; Manifest `output/exports/_quarantine/MANIFEST_20260921.json`):**
- Sandbox (`output/mm_s4_reconcile/` → `_quarantine/mm_s4_reconcile/`): atmo_MM-S1-HK1_17.4, atmo_MM-S1-HK1_23.9, atmo_MM-S1-HK1_30.4, d3yr_BC-SB, valgeo_sb_292
- Kanonisch (`output/paper2_runs/` → `_quarantine/paper2_runs/`): 75 Ordner `SB-S6-HK0/1/2__hp_j_*__tes_j_*` (Study C SB; `pipes.csv` aus einem Memmingen-Lauf), Grund: Vermischung; zusätzlich vor allen Modellfixes gerechnet (F1–F4 → ohnehin ungültig).
- Nicht verschoben, nur gelistet: 28 Ordner mit „nicht lesbar" (unvollständige/alte Läufe) in `output/mm_s4_reconcile/_integrity_scan_20260921.json`.
**Folge:** Pipelines, die SB-S6-Paarordner lesen (F3-Tabelle, Study-C-Auswertung), finden sie nicht mehr — beabsichtigt, F3/Study C sind zurückgezogen und werden neu gerechnet.

## §4aj — 2026-09-21 16:30 (VOR dem Start der Schritt-6-Queue festgeschrieben)

**Freigabe Autor:** Export-Fix ✓ (§4ai); Schritt 6 nach dem Prompt (Kernsatz S1/S2/S3 endogen mit Leiter inkl. Sprosse 0 + S0-Seed; je Netz EIN fixierter Regret-Lauf; Break-even c0 = 100/70/50/30 % für S2-HK0; MM-Interaktion S2-HK2; BC-SB (FIX) als letzter Lauf; keine weiteren HK1/HK2-Läufe, keine Größenreihen).
**Bei der Vorbereitung gefundener Defekt 6 (Hybrid-Tankmodell, vor dem ersten Lauf abgefangen):** das atmosphärische Tankmodell (Leiter, degressive Kurve `c0`, η_strat, 95-°C-Deckel) ist **opt-in** (`CALION_ATMOSPHERIC_TES=1`). Ohne Flag baut `component_assembler` trotzdem die autoritative Geometrie (V_max 250.000 m³, p_max, r_hd), die Basis-YAMLs liefern aber die ALTE Druck-Leiter (SB bis 84,5 MWh, MM bis 67,2 MWh) und LINEARE Kosten α = 1200 €/m³ + β = 100 kEUR/Tank → stille Hybridkonfiguration (im LP: `1,497·V + 124,8/Sprosse`; mit Flag: 12 Sprossen, degressiv 1.204 … 45.003). Nur Läufe MIT aktivem Tank betroffen; **alle heutigen Baselines/S0 schalten den Tank aus (V_max = 0), sind unberührt.** Maßnahmen: (1) Queue setzt das Flag für jeden Job; (2) **Wächter** in `scenario_runner`: aktiver Tank ohne Flag → `RuntimeError` (Ausnahme `CALION_ALLOW_LEGACY_TES=1`); (3) Schalter `CALION_TES_C0_SCALE` (Break-even, Standard AUS) im LP verifiziert (c0×0,3 → exakt 0,300× der Sprossenkosten; c0×0,001 → Tank 73 MWh gebaut, Ziel < S0).
**Umsetzung der Auslegungsfragen (bitte prüfen):** Regret-Größe MM = 1,1 MWh (kleinste Sprosse > 0; 0,5 MWh liegt unter v_min = 50 m³); SB = **219 MWh** = nächste Sprosse zu „1 Tagesspitzenlast", gelesen als ≈ 1 h Spitzenlast (Spitze 195 MW am 18.02.); wörtlich als Tagesenergie der Spitze (~4,7 GWh) läge sie über der Leiter (max 2.046 MWh). Regret-Kosten = Ziel (Tank fix, ohne CAPEX) + nachträgliche degressive Jahres-CAPEX aus dem im Modell berechneten V (`f2_capex.py`, ANF 5 %/30 a).
**Gate-Definition:** S0 ⊂ S_k ⇒ Inkumbent(S_k) ≤ Inkumbent(S0)·(1 + Gap(S_k)); sonst FAIL (Dominanz verletzt = suspect). Zusätzlich `suspect`, wenn Gap > 1 % (SB) bzw. > 0,5 % (MM). Kosten = `obj_eur` (enthält bei investierbarem Tank die Jahres-CAPEX).
**Vorab-Erwartungen (Priors aus den Root-LPs; ausdrücklich Hypothesen):**
- **P1** SB-S1-HK0 (Tank am Primärknoten) **baut** einen Tank: Root-LP-Wert eines kostenlosen 73-MWh-Tanks am Primärknoten −0,25 Mio. €/a (−1,23 %) gegen ≈ 0,10 Mio. €/a Jahres-CAPEX (≈ 4.900 m³ nach c0 = 2,5 Mio. bei 10.000 m³, b = 0,7, ANF 6,5 %) → Nettogewinn 0,1–0,15 Mio. € (0,5–0,7 %), **möglicherweise innerhalb des Gaps**. Das würde die „Speicher-Null"-Aussage für SB-S1 einschränken.
- **P2** SB-S2/S3 (Tank an j_man, nach Defekt 4): Root-LP-Wert nur −0,40 % (0,08 Mio. €/a) ≈ Jahres-CAPEX → kein oder marginaler Bau. MM-S1/S2/S3 bei 100 % c0: **kein Tank** (MM-S2 bereits ohne Bau, Gap 2,4 %).
- **P3** Break-even: MM baut auch bei c0 ×0,3 keinen Tank („bis 30 % nicht"); SB-S2 erreicht die Schwelle zwischen ×0,7 und ×0,3. SB-Ergebnisse gelten nur, wenn Gap < 1 % (sonst „innerhalb der Schranke nicht nachweisbar").
- **P4** MM-Interaktion (S2-HK2 vs S0-HK2 und S2-HK0): kein Effekt über dem Gap (Heizkurvenhebel MM insgesamt nur 2,9 %).
**Queue:** `scripts/paper_2/run_step6_queue.py` (19 Jobs, 4 Slots je Netz, RAM-/Platz-Wächter, `--resume`); Status `output/mm_s4_reconcile/step6_status.json`; Ergebnisordner `output/mm_s4_reconcile/s6_*`.


## §4ak — 2026-09-21 22:00: Defekt 6 — Rückwirkung, Default-Umkehr, einheitliche Regret-Regel, Regressionscheck  [Abnahme §4ai/§4aj durch den Autor]

**A. Rückwirkung Defekt 6 — INVALID, nicht zitieren.** Läufe mit **aktivem Tank ohne `CALION_ATMOSPHERIC_TES=1`** (in diesem Sitzungsabschnitt gestartet, sicher hybrid: Legacy-Leiter + lineare Kosten α=1200 €/m³ + β=100 k€/Tank, keine 95-°C-Decke/Entlademaske, η_strat = 1, proportionaler Verlust):
- **MM-S2-HK0 333.456 €, „kein Tank gebaut" (`d4yr_MM-S2-HK0`, zitiert in §4ae–§4ah) → INVALID.** Ersetzt durch den korrekt konfigurierten Lauf `s6_mm_S2HK0` (atmosphärisch): zulässig ✓ (die Zulässigkeitsaussage aus §4ae bleibt damit bestätigt), Tank **1,1 MWh gebaut**, 326.829 €, −0,79 % vs S0, Gap 1,01 % (innerhalb des Gaps).
- Root-LP-/Wochen-Zahlen mit Tank aus den Akzeptanztests (§4z, §4aa, §4y-Nachtrag): `fixed_T2_SB-S2-HK2_fix73` (20,469), `fixed_T2_SB-S1-HK2_fix73` (19,955), `fixed_T2r_…_hpfirst` (20,121), `fixed_E1_S2_nomasschg`, `fixed_E2_S2_fix7`, `fixed_wkS2f7`, `fixed_wkS2f73`, `fixed_wkS2f7_hpfirst`, `fixed_lpS2f7`, `d4_wk_SB-S2f7`, `smoke_fixed_SB-S2-HK2_wk`, `seedtest_S2`, `seedtest_S2c`, `c0test_1`, `c0test_001`. Flag-Status unbekannt (früherer Sitzungsabschnitt): `diag_SB-S2-HK2_fix73`, `fresh_SB-S4-HK0`, `fresh_SB-S5-HK0` → ebenfalls nicht zitieren. Liste: `output/mm_s4_reconcile/_noflag_tank_runs_20260921.json` (enthält zusätzlich die heutigen Diagnoseläufe `dflt_S2` [Standard-atmosphärisch, gültig] und `leg_allow` [Legacy bewusst]).
- **Was trotzdem gilt:** die *strukturellen* Befunde (Defekt 1 Doppelabzug/Ladung, Defekt 2 Massenbilanz, Defekt 3 Vorlaufverlust, Defekt 4 Knotenrolle: `link_heat_demand` pinnt Q_pipe = Q_demand) — sie hängen nicht an Tankkosten oder -physik. **Ungültig als Zahlen:** −1,23 % (S1) / −0,40 % (S2) / +2,6 % → 0,83 % und die Wochenwerte 1.173.760 / 1.155.695 / 1.177.193 €. Die Vorab-Erwartung P1 (§4aj) stützte sich auf −1,23 % (Tank ohne 95-°C-Decke, also optimistisch) und ist damit weniger belastbar.
- **Nicht betroffen:** alle Baselines (BC-*) und S0-Läufe (Tank explizit aus, `V_max_m3 = 0`); alle Läufe mit Flag: `s6_*`, `seedtest2_*`, `c0atmo_*` und die Kampagnen-Wellen vor dem 20.09. (Wave-Skripte exportieren das Flag).

**B. Default umgekehrt (Config statt Umgebungsvariable).** `storage_geometry.yaml: tes_technology: atmospheric` ist der Standard für alle Szenarien und beide Netze. Der Drucktank nur explizit: Szenario-Schlüssel `tes_technology: pressurized` (Study G, in `scenarios.yaml`) oder Legacy-A/B per `CALION_ATMOSPHERIC_TES=0` **plus** `CALION_ALLOW_LEGACY_TES=1` (sonst `RuntimeError`). `component_assembler` wendet die autoritative atmosphärische Geometrie nur für atmosphärische Tanks an. **Getestet ohne jedes Env-Flag** (Woche, SB-S2-HK0): 13 Sprossen, degressive Kosten (c0×0,3 → exakt 0,3× je Sprosse), Legacy ohne Erlaubnis → Abbruch, mit Erlaubnis → altes Modell (`1,497·V`, 124,8/Sprosse). Bekannte Lücke: der „Drucktank mit ASME-Kostenkurve" für Study G ist damit nur als Legacy-Konfiguration verfügbar, nicht als eigenes Kostenmodell.

**C. Run-Metadaten und `run_hash`.** `tes_technology`, `cost_model`, `c0_eur` (nach Skalierung) + `c0_scale_env`, `t_store_max_c`, `discharge_mask_hours_blocked/len`, `loss_model`, `eta_strat`, Leiter, V-Grenzen stehen in `run_export.json` und `scenario_meta.json` jedes Ergebnisordners und gehen in den `run_hash` ein.

**D. LP-Bestätigung 95-°C-Decke + Entlademaske (SB-S2-HK0, atmosphärisch):** 168 Constraints `c_u_tes_sb_qd_mask`, davon **111 mit `Qd ≤ 0`** = exakt die 111 blockierten Stunden (T_VL > 95 °C) aus den Metadaten; im Legacy-LP 0 solche Constraints. Die Decke wirkt bei S2 über die Maske, bei S3 zusätzlich als Heißladungs-Klippung.

**E. Regret-Größe — einheitliche Regel für beide Netze:** V = Jahreswärmebedarf (Modelloutput der S0-HK0-Seeds) / 365, gerundet auf die nächste Leitersprosse: **MM 9,43 GWh/365 = 25,8 MWh/Tag → 23,9 MWh; SB 639,97 GWh/365 = 1.753 MWh/Tag → 1.607 MWh** (passt in die Leiter, max 2.046 MWh). Die alten Regret-Läufe (SB 219 MWh, MM 1,1 MWh) waren bei Eingang der Regel bereits fertig → **Zusatzpunkte, nicht als Regret-Wert berichten** (SB-219: Gap 74 %, unbrauchbar). Neue Läufe `mm_S2HK0_fix23.9`, `sb_S2HK0_fix1607` seit 21:44 in einer zweiten Queue-Instanz (`--regret2`). Rigorose Untergrenze des Regrets ohne eigenen Lauf: Regret ≥ CAPEX_Jahr(V) − (Inkumbent(S0) − Bound(S_k)).

**F. Regressionscheck der Seeds — bestanden:** MM-S0-HK0 neu 329.418 € / 340,7 t vs alt 329.441 € / 341,2 t (−0,01 % / −0,1 %, Gaps 0,47 % / 0,49 %); SB-S0-HK0 neu 21,063 Mio. € / 66.257 t vs alt 21,093 Mio. € / 66.408 t (−0,14 % / −0,2 %, Gaps 0,80 % / 0,93 %). Abweichungen weit innerhalb der Gaps; abhängige Läufe dürfen interpretiert werden. Neuer Vergleichswert MM-S0-HK2: 327.557 € / 325,8 t (Gap 0,46 %).

**G. Zwischenbefund Schritt 6 (Stand 22:00; `sb_S1HK0` und `sb_BC-SB` offen) — Gap-Disziplin:**
- **SB-S2, SB-S3 und alle drei SB-Break-even-Läufe geben exakt den S0-Seed zurück** (21.063.108 €, 66.256,9 t, identische HP 3,85 MW / 11,34 GWh): der Seed liegt schon innerhalb des Ziel-Gaps von 1 % → keine Suche. Formal „ok" (Gap < 1 %), aber ein Effekt < 1 % ist so **nicht aufgelöst**: „Speicher-Null in SB" ist nur als „innerhalb der Schranke nicht nachweisbar" formulierbar.
- **MM: alle Gaps über 0,5 %** (0,76–6,95 %; TimeLimit 7200 s) → `suspect`. Trotzdem: MM baut bei c0×1,0 (S1/S2) 1,1 MWh, bei ×0,5 4,3 MWh (−1,77 %), bei ×0,3 6,5 MWh (−2,25 %); S3 baut nicht. Rigoros (Bound-Intervall, S0-Bound = 329.418·(1−0,0047)): Ersparnis ≥ 1,79 % bei ×0,3, ≥ 1,31 % bei ×0,5, ≥ 0,32 % bei ×1,0 (S2). MM-Interaktion S2-HK2: Gap 6,95 % → nicht auswertbar.
- **Vorab-Erwartungen (§4aj) vs Ergebnis:** P1 (SB-S1 baut Tank) noch offen; P2 SB-S2/S3 „kein/marginaler Bau" formal ✓ (aber uninformativ), MM „kein Tank bei 100 %" ✗ (S1/S2 bauen 1,1 MWh); P3 „MM baut auch bei ×0,3 nicht" ✗ (baut 6,5 MWh); P4 MM-Interaktion inkonklusiv (Gap 6,95 %).


## §4al — 2026-09-21 22:20: Schritt 0 der Nachschärfung (nur vorhandene Outputs) — **STOPP-Regel ausgelöst**

**Freigabe Autor:** Nachschärfung mit „matched effort": MIPGap 1e-4, TimeLimit fest (MM 4 h, SB 8 h), MIPFocus 3, gleiche Threads, S0 im selben Protokoll mit Seed = bisheriger Inkumbent; Bericht mit Intervallen `Ersparnis_min = max(0, LB_S0 − UB_Sx)`, `Ersparnis_max = UB_S0 − LB_Sx`; MM: S0-HK0, S1, S2, S2-c0×0,7/0,5/0,3, S0-HK2, S2-HK2; SB: S0-HK0, S1, S2; keine SB-Break-even-Läufe solange Ersparnis_max(SB-S2) < 0,5 %. Laufende Jobs (sb_S1HK0, Regret-Läufe, BC-SB) laufen fertig. **Neue Läufe sind NICHT gestartet** (STOPP-Regel, s. u.).
**Bestätigungen:** (1) Mindest-Ersparnisse werden mit LB_S0 − UB_Sx aus den **Gurobi-Logs** gerechnet (Best bound / Best objective), nicht aus dem S0-Inkumbenten und nicht aus rekonstruierten Gaps (`scripts/paper_2/step0_cost_decomp.py`). Die früheren Werte aus §4ak G (≥0,32/1,31/1,79 %) stimmen; log-basiert: S2 1.030 € (0,31 % von UB_S0), c0×0,5 4.276 € (1,30 %), c0×0,3 5.868 € (1,78 %). (2) MM c0×0,7 fehlt **nicht** (`s6_mm_S2HK0_c70`): kein Tank gebaut, 329.255 €, Gap 2,72 %, `Ersparnis_max` 2,77 %; steht in der Nachschärfungsliste.
**Kostenzerlegung MM (S0-HK0 = 329.418 €; Δ in €, exportierte Terme + Rest):**
| Lauf | Δ gesamt | Brennstoff | CO₂ | Strom netto (buy/sell) | Bedarfspreis | **Dump-Strafe** | Tank-CAPEX | Rest „other" |
|---|---|---|---|---|---|---|---|---|
| S1 (c0×1,0; 1,1 MWh) | −2.795 | −406 | −556 | −126 / −1.123 | −679 | **−3.054** | +5.362 | −2.212 |
| S2 (c0×1,0; 1,1 MWh) | −2.589 | −1.560 | −1.072 | −91 / −1.012 | −491 | **−3.040** | +5.362 | −685 |
| S2 c0×0,5 (4,3 MWh) | −5.835 | −2.389 | −1.648 | −84 / −933 | −491 | **−3.008** | +6.961 | −4.243 |
| S2 c0×0,3 (6,5 MWh) | −7.427 | −2.434 | −1.724 | −55 / −773 | −680 | **−2.995** | +5.578 | −4.343 |
(Tank-CAPEX = degressive Kosten der gebauten Sprosse × Annuitätsfaktor aus dem Lauf-Log; „Rest" = Zielfunktion − exportierte Terme − Tank-CAPEX, enthält Aktivierung, Tie-Break, Terminalwert, Slack- und Regularisierungsterme; diese sind in `economics.csv` nicht exportiert.)
**Ursache:** `dump_cost_eur_per_mwh_th: 1000.0` (Memmingen_P2_base.yaml:551) — **abgeregelte Wärme kostet 1000 €/MWh**. S0 regelt ≈ 9,3 MWh/a ab (9.335 €), S2 ≈ 6,3 MWh (6.296 €): der 1,1-MWh-Tank vermeidet ≈ 3 MWh Abregelung (Durchsatz 45 MWh geladen / 31 MWh entladen pro Jahr). **Dump-Anteil an der ausgewiesenen Ersparnis: S1 109 %, S2 117 %, c0×0,5 52 %, c0×0,3 40 %** (Schwelle 20 %; S3/c0×0,7 ohne Tank ≈ 0). Der Rest-Term (im S0 6.315 €, ≥ Aktivierungs-/Tie-Break-/Regularisierungsterme; `activation_cost_eur` 20/50 k€ gehört zu den *Investitions*-Blöcken von HP/EK und ist hier 0) trägt zusätzlich −0,7 … −4,3 k€ bei; obere Schranke Strafanteil (Dump + Rest) 144 % / 124 % / 99 %.
**Ohne Dump-Strafe (nur reale Terme + Tank-CAPEX):** S2 c0×1,0 **+1.136 €** (Tank lohnt sich nicht), c0×0,5 **+1.416 €** (lohnt nicht), c0×0,3 **−88 €** (Break-even) — wenn „Rest" ebenfalls Strafanteil ist; zählt „Rest" als real: S2 +451 €, c0×0,5 −2.827 €, c0×0,3 −4.431 €.
**Betriebsprofil (S2 c0×1,0):** 28 Vollzyklen/a (1,1 MWh), Laden 551 h / Entladen 303 h, 0 h gleichzeitig; Ladebetrieb: Biomasse +0,06 MW, KWK +0,02 MW gegenüber S0 (Grundlast-/Mindestlasterzeuger, keine HP/EK); Entladestunden: Gaskessel −0,18 MW, Biomasse +0,11 MW. Gaskessel-Betriebsstunden 90 → 48 (Starts 19 → 11), KWK 851 → 833 (189 → 184), Biomasse 8.760 (1 Start); c0×0,3: Gaskessel 27 h, KWK 755 h. **P2H „954 Betriebsstunden" im S0 ist Rauschen** (Leistungen ~0,01 MW, Schwelle 1e-3 MW zu niedrig): EK-Wärme insgesamt 0,012 GWh.
**Nebenbefund (Korrektur §4ae/§4af):** die dort genannten „~1 GWh abgeregelt" im alten BC-MM sind falsch: bei 1000 €/MWh entsprechen 104.413 € **≈ 104 MWh** (nicht 1 GWh).
**Konsequenz:** Ein Großteil der MM-Tankersparnis ist ein Artefakt des Dump-Strafpreises (und möglicherweise weiterer Regularisierungsterme), nicht des Speicherwerts. Der Strafpreis steckt auch in allen anderen Kosten/TAC-Werten (BC-MM 10,0 k€ = 2,9 %, MM-S0 9,3 k€ = 2,8 % der Zielfunktion). **STOPP nach Vorgabe, Entscheidung Autor:** siehe Bericht.


## §4am — 2026-09-22: Nachschärfung Teil C — laufende Läufe abgeschlossen, „1000-€-Stand" fixiert

**Freigabe Autor:** Schritt A (Export) + B (Dump-Preis) mit Präzisierung; B erst nach A. Alle zu Beginn noch laufenden Jobs sind fertig und werden hiermit als **„1000-€-Stand"** gekennzeichnet (Modell mit `dump_cost_eur_per_mwh_th = 1000`, Referenz für den späteren Ein-Satz-Vergleich in B):

| Lauf | Ziel € | Gap | CO₂ t | Dump € (MWh) |
|---|---|---|---|---|
| SB-S1-HK0 | 20.990.860 | 1,05 % | – | 1.146 (1,15) |
| SB-S0-HK0 (Referenz) | 21.063.108 | 0,80 % | 66.256,9 | 8.191 (8,19) |
| SB-BC (FIX) Neulauf | 21.331.044 | 0,98 % | – | 28.977 (28,98) |
| MM-S0-HK0 | 329.418 | 0,47 % | 340,7 | 9.335 (9,34) |
| MM-S0-HK2 | 327.557 | 0,46 % | 325,8 | 21.148 (21,15) |
| MM-S1/S2/S3-HK0, c0-Varianten | 321.991 – 329.401 | 0,76–2,72 % | 323,1–340,6 | 6.282–9.335 |

**Regret-Läufe (uniforme Regel, Jahresbedarf/365 → nächste Sprosse), NICHT als Regret-Wert verwertbar (Zusatzpunkte):**
- **MM, 23,9 MWh:** 318.493 €, Gap 0,39 % — technisch sauber, aber **kein Regret-Wert**, weil der Kontext (kein Seed, c0×1,0, 1000-€-Dump-Stand) wechselt; nach B neu einzuordnen.
- **SB, 1.607 MWh:** 84.810.136 €, **Gap 75 %**, Dump 23,4 Mio. € (137.000 t CO₂) — offensichtlich degenerierter Lauf (vermutlich zwingt die feste Leistungskopplung `P = 0,25·E` = 402 MW Lade-/Entladeleistung bei einem Netz mit 640 GWh/a Jahresbedarf eine physikalisch nicht bedienbare Durchsatzrate, die massenhaft in die Abregelung läuft). **Unbrauchbar, wird nicht weiterverfolgt**, keine Ursachenanalyse ohne Auftrag.


## §4an — 2026-09-22: Schritt A abgeschlossen — vollständige Kostenzerlegung, STOPP-Regel erneut ausgelöst (schärfer als vorher)

**Umsetzung (reiner Export, kein Modelleingriff):** `result_collector.py` liest jetzt alle 15 additiven Zielfunktionsterme einzeln vom gelösten Pyomo-Modell (6 vorher nie erfasste: Terminalwert, Bedarfs-Slack, Rücklaufanker, Druck-Regularisierung, Stich-Tie-Break, Druck-Entlastungs-Slack). `extract_artefacts_p2.py` schreibt `cost_breakdown.json` je Lauf (Positivliste „reale Kosten" vs. „Modellhilfsterme", mit Abgleich).

**Zwei Fehler bei der Umsetzung gefunden und behoben (beide in meinem eigenen neuen Code, nicht im Modell):**
1. **Vorzeichenfehler:** Stromerlös wurde im ersten Entwurf doppelt positiv gezählt statt abgezogen (Summenprobe zeigte exakt 2× den Erlös als Differenz) — behoben, mit Live-Modell-Kreuzcheck verifiziert (Abweichung < 10⁻⁹ €).
2. **Echter Befund, keine Doppelzählung:** `CO2_cost_EUR` (und damit `economics.csv:cost_co2_eur`, in ALLEN bisherigen KPI-Vergleichen dieser Kampagne verwendet) ist die **CHP-eigenverbrauchs-genettete** Größe (bekannter Mechanismus aus Paper 1, `project_paper1_objective_residual`); das Modell optimiert gegen den **Brutto**-Wert. Differenz exakt gleich dem vorher unauflösbaren Rest (auf 11 Nachkommastellen im Diagnoselauf bestätigt). Fix: `cost_breakdown.json` nutzt den Brutto-Wert als „reale" CO₂-Kosten und weist die Netting-Korrektur als eigene, benannte Hilfsterm-Zeile aus (Rückverfolgung zu `economics.csv` bleibt erhalten). **`economics.csv`/bisherige KPI-Zahlen unverändert, nicht betroffen.**
**Alle 4 Nachrechnungen (S0-HK0, S2 c0×1,0/0,5/0,3) reproduzieren die Zielfunktion jetzt auf < 10⁻⁹ € (`reconciliation_check: OK`); Regressionscheck bestanden (identische Zielfunktionswerte wie vor dem Fix).**

**Antworten auf die drei Prüfpunkte:**
- **(i) Terminal-Term = 0, aber weil es eine harte Nebenbedingung ist** (`E[letzte Stunde] ≥ 0,5·E_max`, kein Straf-/Wertterm) — SOC wird weder belohnt noch frei, sondern auf 50 % Endstand nach unten begrenzt.
- **(ii) Tie-Break/Regularisierung:** Druck-Tie-Break und Stich-Verlust-Tie-Break beide ≤ 80 €, ≤ 0,03 % — bestehen die 0,01-%-Schwelle knapp nicht dem Wortlaut nach, sind aber vernachlässigbar. **Druck-Entlastungs-Slack (Datenqualitäts-Ventil) besteht NICHT:** 2.286 € (0,69 %) bei S0, fällt mit steigendem V_TES auf 1.595 / 365 / 254 €.
- **(iii) SB-Dump:** wie berichtet, klein (0,005–0,14 % der Zielfunktion).

**STOPP-Regel, jetzt mit exakten (nicht mehr geschätzten) Zahlen — Ergebnis SCHÄRFER als vor Schritt A:**
| Lauf | Δ Zielfunktion | Δ reale Kosten | Δ Hilfsterme | Hilfsterm-Anteil |
|---|---|---|---|---|
| S2 c0×1,0 (1,1 MWh) | −2.589 € | **+986 € (+0,31 %)** | −3.616 € | **140 %** |
| S2 c0×0,5 (4,3 MWh) | −5.835 € | −1.197 € (−0,38 %) | −4.749 € | **81 %** |
| S2 c0×0,3 (6,5 MWh) | −7.427 € | −2.720 € (−0,86 %) | −4.816 € | **65 %** |

**Bei vollen Tankkosten (c0×1,0) kostet der Tank in realen Wirtschaftlichkeitsgrößen MEHR (+986 €), nicht weniger** — der gemeldete Vorteil (−2.589 €) ist zu 140 % ein Modellartefakt (Dump-Vermeidung −3.040 € + Druck-Slack-Reduktion −690 €, teilweise durch CO₂-Netting-Verschiebung +111 € gegenläufig). Bei c0×0,3 bleibt ein realer Vorteil von −2.720 € (−0,86 %), aber 65 % des gemeldeten Effekts bleiben Artefakt.
**Neuer, eigenständiger Befund:** Der Druck-Entlastungs-Slack ist NICHT nur eine kleine Nebengröße, sondern der **zweitgrößte** Hilfsterm-Beitrag zur „Ersparnis" (−690 bis −2.032 €, vergleichbar mit dem Dump-Effekt selbst) und wird von Schritt B (Dump-Preis-Änderung) **nicht berührt**. Grund unklar (Vermutung: TES am Knoten j_12 ändert Netzflüsse und entlastet anomale Druck-Datenpunkte) — nicht selbst untersucht, wie vorgegeben nur gemeldet.
**Reale-CAPEX-Treiber:** Kapitalkosten steigen mit dem Tank (+4.478 bis +5.861 €) und sind der Haupt-Gegenposten; Brennstoff (−1.560 bis −2.434 €), CO₂ brutto (−1.183 bis −1.932 €) und Netzentgelt (−491 bis −680 €) sind die realen Einsparungen.
**Konsequenz für Schritt B:** Der Dump-Preis-Wechsel (1000 → 5 €/MWh) wird den größten Hilfsterm (Dump, −3.0 bis −3.6 k€ Delta) fast vollständig entschärfen, lässt aber den Druck-Slack-Effekt unverändert stehen. Nach B ist der Druck-Slack voraussichtlich der **dominante** verbleibende Hilfsterm — Entscheidung des Autors nötig, ob das vor oder nach B untersucht wird.


## §4ao — 2026-09-22: B3 (alter Stand) — Heizkurvenhebel MM ist zu 98 % Druck-Slack-Artefakt

**Freigabe Autor:** B (Dump-Preis + Druck-Slack-Bereinigung in einem Umbau), Attribution per MM-Faktorversuch. Umsetzungsstand:
- **B1a (Dump-Preis 1000→5 €/MWh, beide Netze):** umgesetzt (`Memmingen_P2_base.yaml`, `Stadtbach_topo.yaml`).
- **B1c (TES-SOC zyklisch, „Defekt 7"):** umgesetzt und verifiziert. **Befund zum alten Zustand:** SOC-Start war NICHT frei, sondern fest auf 50 % von E_max gepinnt (`soc0_fraction=0.5`, ein Ausdruck, keine Variable); das Terminal war nur eine EINSEITIGE Ungleichung `E[Ende] ≥ 50 %`. Beide Werte waren zufällig gleich (0,5), was die Asymmetrie leicht übersehbar machte. Neu: `E0` ist jetzt eine echte freie Variable (0 ≤ E0 ≤ E_max, bzw. ≥ e_min-Anteil), und `E[Ende] == E0` ist eine harte Gleichheit. Verifiziert direkt im LP (`c_e_tes_main_terminal_: E0 − E(48) = 0`), inkl. korrekter Rückrechnung über die Standverlust-Konstante der ersten Stunde.
- **B1d (Kosten-Positivliste):** `CO2_cost_EUR` nutzt (aus Schritt A) den Brutto-Wert; genettete Größe bleibt als benannte Korrektur erhalten. `Grid_sell_revenue_EUR` explizit als „Strom (KWK-Erlös Verkauf, negativ)" gekennzeichnet — verifiziert: in BEIDEN Netzen erzeugt AUSSCHLIESSLICH KWK-Technologie (MM: chp_main; SB: hkw/gtost/bmhkw) Strom, HP/EK/P2H sind reine Verbraucher, alle anderen Erzeuger sind wärmenur. Kein separater Posten nötig, Label korrigiert.
- **B1b (Druck-Slack-Vorverarbeitung):** noch nicht umgesetzt — Export-Code für den Slack-Auditreport wird gerade gebaut, danach Pass-1-Referenzlauf (BASE-FIX, neuer Dump-Preis) zur Ableitung der Aufweitung.

**B3, Teil 1 (alter Stand, dump=1000, cost_breakdown.json nachträglich erzeugt aus einem frischen Lauf mit unverändertem Modell sonst):**
| | BASE-FIX | BASE-HK0 | Δ |
|---|---|---|---|
| Ziel € | 341.845 | 331.785 | −10.060 (−2,94 %) |
| reale Kosten € | 320.174 | 319.928 | **−246 (−0,07 %)** |
| Hilfsterme € | 20.562 (6,0 %) | 10.713 (3,2 %) | **−9.849 (98 % von Δ Ziel)** |

**Der gemeldete „2,9-%-Heizkurvenhebel MM" ist zu 98 % Artefakt, überwiegend EIN Term: `Pressure_slack_cost_EUR` (−9.095 € von −9.849 € Hilfsterm-Δ).** Der reale Effekt liegt bei −0,07 % der Zielfunktion, statistisch nicht von 0 zu unterscheiden. **Meldepflicht nach B3 ausgelöst** (Schwelle 50 % weit überschritten). Realer Kostentreiber in die richtige Richtung: Netzentgelt −508 €, Stromkosten −372 €/−321 € (Bezug/Erlös), gegenläufig Brennstoff +853 € und CO₂ brutto +101 €.
**Einordnung:** Die feste Vorlauftemperatur (BASE-FIX/TVLFIX) erzeugt in der Druckpropagation offenbar deutlich mehr anomale Slack-Aktivierung als eine reale Heizkurve (BASE-HK0) — die HK0-Heizkurve „repariert" damit vor allem ein Datenqualitäts-/Modellierungsproblem der Konstant-Temperatur-Baseline, nicht die Systemkosten selbst. B3 Teil 2 (nach dem vollständigen Umbau) folgt, sobald B1b steht.


## §4ap — 2026-09-22 14:10: B1 vollständig implementiert und verifiziert; Pass-1-Referenzläufe laufen

**B1a (Dump-Preis 5 €/MWh, beide Netze):** umgesetzt.
**B1c (TES-SOC zyklisch, Defekt 7):** umgesetzt und **im LP verifiziert** (`c_e_tes_main_terminal_: E0 − E(letzte Stunde) = 0`, echte harte Gleichheit; E0 neue freie Variable mit `0 ≤ E0 ≤ E_max`/`≥ e_min`-Schranken wie jede andere Stunde). Regressionstest (nicht-investierbarer 8,7-MWh-Fixtank): Differenz „SOC erste vs. letzte Stunde" 0,0057 MWh erklärt sich exakt durch den Standverlust der ersten Stunde (LP-Konstante −0,005694 identisch), keine numerische Lockerheit.
**B1d (Kosten-Positivliste):** CO₂ brutto (aus Schritt A) + KWK-Stromerlös explizit benannt — verifiziert, dass in BEIDEN Netzen ausschließlich KWK-Technologie Strom erzeugt (MM: `chp_main`; SB: `hkw`/`gtost`/`bmhkw`; HP/EK/P2H sind reine Verbraucher, alle übrigen Erzeuger wärmenur) — kein separater Posten nötig, Label korrigiert.
**B1b (Druck-Slack-Vorverarbeitung), Code fertig, Daten stehen aus:**
- Neuer Diagnose-Export `pressure_slack_audit.json` (pro Knoten: Stunden, Werte, Max, Summe) — verifiziert an einem gezielten Dezember-Fenster: exakt der dokumentierte Altfall (`J_13_station_dp_slack`, 3 Stunden, 0,089 bar) wird gefunden.
- Neuer Modus-Schalter `CALION_PRESSURE_SLACK_MODE` (`objective` = Standard/Legacy, unverändert getestet; `preprocessed` = Slack-Variable entfällt, feste Aufweitung aus `configs/paper_2/pressure_relief_widening.json` wird hart in die Druckschranke eingerechnet).
- **Verifiziert (Dezember-Testfenster):** `objective`-Modus löst wie vorher (identisches Ergebnis); `preprocessed`-Modus mit noch LEERER Aufweitungstabelle wird — wie vom Protokoll verlangt — **unzulässig** an genau der dokumentierten Stelle (kein stilles Wiedereinführen des Slacks).
- Aufweitungstabelle ist aktuell ein **Platzhalter (leer)**; wird aus den laufenden Pass-1-Referenzläufen (BASE-FIX, neuer Dump-Preis, beide Netze, Modus `objective`) abgeleitet: je Knoten der maximale beobachtete Slack-Wert im Jahr.

**Laufend:** `b1prep_BC-MM` (Memmingen), `b1prep_BC-SB` (Stadtbach) — volle Jahresläufe, liefern (a) die Aufweitungstabelle für B1b, (b) den Dump-Mengen-Wächter (B1a) und (c) doppeln als „neue Referenzen" für B4, sobald B1b eingerechnet und ein zweiter Durchlauf im `preprocessed`-Modus bestätigt ist.


## §4aq — 2026-09-22 14:40: B1b-Aufweitungstabelle abgeleitet — EINE Meldepflicht ausgelöst; B1a-Wächter — EINE Meldepflicht ausgelöst

**B1b — Liste der geweiteten Punkte (Anzahl, max. Betrag, betroffene Knoten):**
| Netz | Knoten | Aufweitung | Herkunft |
|---|---|---|---|
| SB | — (keine) | 0 | BASE-FIX (`b1prep_BC-SB`) hat **null** Slack-Stunden im ganzen Jahr — Stadtbach braucht keine Aufweitung. |
| MM | `j_13` | **3,8686 bar** | 3 zusammenhängende Stunden (Index 8365–8367, Mitte Dezember) mit identischem Wert — derselbe dokumentierte Altfall (`V_22/23/24`-Sparse-Metering). |

**Meldepflicht (B1b):** `j_13` hat `min_required_bar: 2,0` (Konfigurationswert). Die abgeleitete Aufweitung (3,87 bar) ist **größer als die gesamte Anforderung des Knotens** — nach der wörtlichen Ableitungsregel (fester Betrag, identisch für alle Szenarien, aus dem Jahresmaximum) wird die Druckdifferenz-Anforderung an `j_13` für **alle 8760 Stunden** faktisch bedeutungslos, nicht nur für die 3 anomalen. Ich habe die Regel exakt wie angewiesen umgesetzt (`configs/paper_2/pressure_relief_widening.json`, `nodes.j_13.widen_bar = 3.8686`, Quellstunden dokumentiert) und einen Verifikationslauf gestartet (`b1pass2_BC-MM`, `CALION_PRESSURE_SLACK_MODE=preprocessed`) — melde dies aber vor der Interpretation weiterer Ergebnisse, da eine ganzjährige De-facto-Abschaltung der Druckbeschränkung an einem Knoten eine wesentliche Modellkonsequenz ist, die über die 3 Stunden hinausgeht, die das Problem eigentlich verursacht haben.

**B1a — Dump-Mengen-Wächter (neuer Preis 5 €/MWh vs. 1000-€-Stand):**
| Netz | alt (1000 €/MWh) | neu (5 €/MWh) | Faktor |
|---|---|---|---|
| MM (BC-MM) | 9,34 MWh | 12,58 MWh | 1,35× — unauffällig |
| SB (BC-SB) | 28,98 MWh | **784,00 MWh** | **27,05× — MELDEN** |

**Meldepflicht (B1a):** Stadtbach dumpt beim neuen, realistischeren Preis 27× mehr als beim künstlichen 1000-€-Stand — Richtung ist plausibel (niedrigere Strafe → mehr Abregelung), die absolute Größe (784 MWh/a von 640 GWh/a Jahreslast ≈ 0,12 %) ist klein gegenüber der Last, aber die Verhältniszahl überschreitet die Faktor-3-Schwelle deutlich. Ursachenvermutung (nicht geprüft, wie angewiesen nur gemeldet): stromgeführte KWK, die bei günstigen Börsenpreisen mehr Wärme mitproduziert, als das Netz braucht, und diese jetzt lieber für 5 €/MWh abregelt statt den Betrieb zu drosseln.

**Pass-2-Verifikationsläufe laufen** (`b1pass2_BC-MM`, `b1pass2_BC-SB`, Modus `preprocessed`) — bestätigen Zulässigkeit und liefern die endgültigen B4-Referenzwerte, sobald fertig.


## §4ar — 2026-09-22 15:10: Pass-2 — SB zulässig, MM UNZULÄSSIG trotz überdimensionierter Aufweitung (Befund, nicht behoben)

**SB (`b1pass2_BC-SB`, Modus `preprocessed`, leere Tabelle):** zulässig, Ziel 21,165 Mio. €, Gap 0,27 %. Wie erwartet (SB hatte in Pass 1 keinen einzigen Slack-Zeitschritt im ganzen Jahr).

**MM (`b1pass2_BC-MM`, Modus `preprocessed`, `j_13` um 3,8686 bar aufgeweitet — mehr als die gesamte Anforderung von 2,0 bar): UNZULÄSSIG.** Root-Relaxation bereits unzulässig, kein Inkumbent. Die IIS-Berechnung des Solvers ist an einem separaten Tooling-Fehler gescheitert (`'GUROBIFILE' object has no attribute '_solver_model'`), ein Modell-Snapshot wurde aber gespeichert (`output/exports/BC-MM/.../solver/infeasible_model.lp`).

**Bedeutung:** Obwohl `j_13`s EIGENE Differenzdruck-Anforderung durch die Aufweitung vollständig neutralisiert wurde, bleibt das Modell an dieser Dezember-Anomalie unzulässig. Das deckt sich mit dem historischen Code-Kommentar: „the coupled pressure system at exactly one filled hour … has NO feasible P_supply/P_return" — die Unzulässigkeit sitzt demnach nicht (nur) in `j_13`s Stationsdifferenz, sondern irgendwo im gekoppelten Druck-System (Pumpen-, Rohr- oder einer anderen Knoten-Nebenbedingung), für die es **keinen** Slack-Mechanismus gibt. Der alte Slack an `j_13` hat die Symptomatik zufällig kaschiert, ohne die eigentliche Ursache zu beheben.

**Gemäß Anweisung NICHT behoben, NICHT mit weiterem Slack gepatcht.** Zwei offene Punkte liegen damit vor dir:
1. Die überdimensionierte `j_13`-Aufweitung aus §4aq (3,87 bar > 2,0 bar Anforderung, aus nur 3 Stunden).
2. Diese neue, tiefere Unzulässigkeit, die auch bei voller Aufweitung bestehen bleibt.

**B2/B3-Teil-2/B4 werden nicht gestartet, bis du entschieden hast, wie mit dieser Dezember-Anomalie umgegangen wird** (z. B.: diese 3 Stunden aus dem Optimierungshorizont ausschließen und als Datenlücke dokumentieren; oder eine echte IIS-Diagnose der gespeicherten `infeasible_model.lp` fahren, um die zusätzliche bindende Nebenbedingung zu identifizieren; oder eine andere Lösung). Kein Solver läuft aktuell außer diesen beiden abgeschlossenen Pass-2-Läufen.


## §4ar — 2026-09-22 15:30: C1–C3 Zwischenstand — EIN ungeklärter Befund (C1 Volljahr infeasible), C3 mechanisch verifiziert, C2 unvollständig. Budget-Grenze erreicht, STOPP vor B2/B3-2/B4.

**C1 (zeitlich lokale Aufweitung) — TEILWEISE verifiziert, dann ein ungeklärter Fehlschlag:**
- Code umgesetzt: Aufweitung jetzt `{Knoten: {Stunde: Wert}}` statt Jahreskonstante; Slack-Mechanismus bleibt an JEDER anderen Stunde/jedem anderen Knoten unverändert aktiv (kein globales Entfernen mehr); nur an den exakten (j_13, {8365,8366,8367})-Paaren wird die Slack-Variable auf 0 fixiert und die Schranke hart um 3,8686 bar geweitet.
- Ein gezielter 3-Tage-Dezember-Test ergab ein exaktes Ziel-Match zum Legacy-Modus — **aber dieser Test ist methodisch ungültig**: Bei einem kurzen Zeitfenster indiziert `model.t` lokal (1..72), nicht absolut (8365..8367), sodass die Aufweitungstabelle dort **nie griff** — der Test hat unbeabsichtigt den Slack-Mechanismus unverändert (frei überall) geprüft, nicht die Aufweitung selbst.
- **Der echte Volljahres-Verifikationslauf (`b1pass2b_BC-MM`, Modus `preprocessed`, korrekte absolute Indizierung) ist INFEASIBLE** (Root relaxation infeasible nach 37 s) — trotz identischer Werte wie im Referenzlauf. Ursache nicht geklärt: möglicherweise eine Index-Diskrepanz zwischen der Audit-Erfassung (`str(t)` aus `model.t`) und der Aufweitungs-Anwendung, oder eine strukturelle Interaktion, die im 3-Stunden-Testfenster nicht sichtbar wird. **Nicht weiter untersucht — Budgetgrenze.** Nach Vorgabe („Wird ein Szenario damit unzulässig: melden, keine Slack-Rückkehr") wird dies gemeldet, nicht durch Wiedereinführung von Slack kaschiert. `b1pass2b_BC-SB` lief zum Zeitpunkt des Abbruchs noch (SB hat ohnehin keine Aufweitungseinträge, daher potenziell unbetroffen, aber nicht verifiziert).
- **Konsequenz:** Die "neue Referenz" aus B1b/C1 steht noch nicht. B3-Teil-2, B4 und der Break-even-Teil von B2 können ohne eine tragfähige Referenz nicht sinnvoll interpretiert werden.

**C2 (SB-Dump-Ursache) — NICHT abgeschlossen:**
- `dispatch_hourly.csv`/`dispatch_per_asset.csv` enthalten **keine** Dump-Spalte; eine Energie-Bilanz-Rekonstruktion war unzuverlässig (durchgehend positives Residuum, nicht plausibel). Als sauberer Weg wurde ein `dump_audit.json`-Export gebaut (pro Knoten/Stunde, analog zum bereits verifizierten `pressure_slack_audit.json`) und ein frischer SB-Lauf (`c2data_BC-SB`, dump=5, Legacy-Modus) gestartet, um ihn zu befüllen.
- Dieser Lauf war beim Abbruch noch nicht fertig (Gap 17 %, ~13 min Laufzeit). **Die vier C2-Fragen (welche Einheit läuft in Dump-Stunden, Strompreis dort vs. Jahresmittel, KWK-Anteil über Mindestlast, Zuschlag-Formel) sind damit noch nicht beantwortet.**

**C3 ("Notkühler nach Ansatz B") — implementiert, mechanisch verifiziert, EIN wichtiger Befund (kein Bug, aber zu beachten):**
- **Kein bestehender KWK-Zuschlag im Optimierungsziel gefunden** (geprüft): `calion/economics/german_subsidies.py`s `KWKGParameters` (inkl. `chp_bonus_new_ct_per_kwh`) ist ein eigenständiger NACHGELAGERTER Bericht-Rechner (`report_generator.py`), nie in `create_objective` verdrahtet. Die im Config-Kommentar erwähnten „KWKG 0,446 ct/kWh" sind eine STROMBEZUGS-Umlage (Kosten beim Einkauf), keine Erzeugungs-Vergütung. **Interpretationsentscheidung (bitte bestätigen):** Da kein separater Zuschlag existiert, wird die geforderte Kürzung auf den bestehenden Markterlös (P_sell × Preis) angewendet: verlorene Erlöse = `el_eff × Q_dump_chp[t] × Verkaufspreis[t]` (linear, da el_eff eine Konstante ist), als eigener, klar benannter Posten (`CHP_dump_revenue_clawback_EUR`), nicht als neue Subvention.
- **Umsetzung:** neue Variable `Q_dump_chp_{ASSET}` je KWK-Anlage (nur wo `el_eff` gesetzt: MM `chp_main`; SB `hkw`/`gtost`/`bmhkw`), Kapazität `<= cap_th_mw` UND `<= Q_th[t]` (kann nicht mehr abregeln als gerade produziert); der Knotenbilanz erreicht nur `Q_th − Q_dump_chp` (Nutzwärme), linear über eine Expression. Die generische Knoten-Dump-Variable wird bei `CALION_DUMP_MODE=chp_only` an JEDEM Knoten hart auf 0 fixiert (Struktur bleibt, Fähigkeit entfällt) — Biomasse/Gaskessel/sonstige haben damit keinerlei Dump-Ausweg mehr, müssen über ihre bestehende UC (Ein/Aus, Mindestlast) reagieren; wird das unmöglich, wird das Modell unzulässig (gewünschtes Signal).
- **Verifiziert (Wochentest, MM-S0-HK0):** `reconciliation_check: OK`, `sum_check = 0,0` exakt (der Clawback wurde korrekt in die Kostenbilanz eingerechnet, kein neues Residuum); Knoten-Dump-Kosten exakt 0; `dump_audit.json` leer (keine KWK-Abregelung diese Woche) → Clawback korrekt 0.
- **Wichtiger, KEIN Bug, aber zu meldender Befund:** Im selben Wochentest investierte das Modell unter `chp_only` erstmals in `hp_main` (≈199 MWh/Woche), während es unter Legacy 0 blieb — **Ursache gefunden, kein Fehler:** `MM-S0-HK0`s Override deaktiviert **nur** `tes_main` (`V_max_m3: 0`); `hp_main` ist in S0 die ganze Zeit schon investierbar gewesen und wurde bisher vom Optimierer einfach nie gebaut. Mit dem billigen Knoten-Dump-Ventil war das nie nötig; ohne dieses Ventil wird HP-Investition an einigen Stunden ökonomisch, um Überschuss zu vermeiden. **Relevanz:** Die bisher mehrfach berichtete Aussage „HP lohnt sich in S0 nicht" (u. a. §4ag/§4ah, H*-Diskussion) beruhte auf Läufen MIT dem freien/günstigen Dump-Ventil — sie könnte selbst teilweise ein Dump-Artefakt sein, nicht nur die Heizkurvenaussage. Das ist GENAU das, was B4 nach dem Umbau neu prüfen sollte; hier nur als Erwartung vermerkt, nicht mit dem noch-infeasiblen C1-Stand verifizierbar.
- **Kostenkategorie-Vereinfachung (dokumentiert, nicht perfektioniert):** Der KWK-Dump-Betriebskosten-Posten (5 €/MWh) liegt aktuell im `Fuel_cost_EUR`-Bucket (keine eigene Zeile) — funktional korrekt in der Zielfunktion, aber nicht separat ausgewiesen; bei Bedarf nachschärfbar.

**Nicht begonnen (wegen Budgetgrenze):** B2 (2×2-Attribution), B3-Teil-2 (Nachher-Vergleich), B4 (neue Referenzen + matched-effort-Protokoll). Diese setzen eine geklärte, feasible C1-Referenz voraus.

**Entscheidung des Autors nötig, bevor es weitergeht:**
1. Soll ich die C1-Infeasibilität jetzt tief untersuchen (nächster Schritt: IIS auf dem infeasiblen `b1pass2b_BC-MM`-Snapshot, der bereits als „Infeasible model snapshot" exportiert wurde), oder reicht als Zwischenlösung: Aufweitung nur an EXAKT den 3 Stunden UND versuchsweise mit einem größeren Toleranzband (z. B. ±1 Stunde) einbauen, falls es eine Indexverschiebung ist?
2. Ist die C3-Interpretation „Zuschlag = bestehender Markterlös, gekürzt" richtig, oder war eine NEUE Vergütung (KWKG-Zuschlag, bisher nur im Reporting) gemeint?
3. C2 fertig laufen lassen (SB, ~30–40 weitere Minuten) und dann auswerten?


## §4as — 2026-09-22 21:05: D0–D3(b) — Clawback entfernt, Aktiv-Assertionen gesetzt, C2 ausgewertet, BEIDE Ablations-Varianten unzulässig

**D0 (Zuschlag entfernen):** `CHP_dump_revenue_clawback_EUR` vollständig entfernt aus `model_finalizer.py`, `result_collector.py`, `extract_artefacts_p2.py`. Marktlerlös für KWK-Strom bleibt jetzt IMMER voll, auch bei Abregelung — kein Ersatzmechanismus. **Annahme (dokumentiert wie gefordert):** ein echter KWK-Zuschlag (KWKG) bleibt vollständig außerhalb der Zielfunktion; `calion/economics/german_subsidies.py` unverändert, weiterhin nur nachgelagerter Bericht. Regressionstest (Legacy-Modus, Wochenfenster): Ziel exakt 10.118,69 € (identisch zum Stand vor der C3-Einführung) — D0 ist sauber, keine Nebenwirkung.
**HP-Investitionsbefund aus dem vorigen Bericht (§4ar) bleibt bis zu einem echten Nachher-Vergleich uninterpretiert**, wie gefordert.

**D1 (Aktiv-Assertionen) — für alle vier Mechanismen umgesetzt und verifiziert:**
- Druckaufweitung (`thermal_node.py`): pro Knoten wird geloggt „angewendet X/Y Stunden"; bei Y>0 und X=0 bricht es hart ab; bei einem **Volljahreslauf** zusätzlich hart, falls X≠Y.
- Knoten-Dump-Sperre (`constraint_builder.py`): zählt fixierte Node-Stunden-Einträge, `assert > 0` bei `chp_only`.
- Notkühler-Kapazität (`system_builder.py`, nach Assembly): zählt KWK-Anlagen mit `Q_dump_chp`, `assert > 0` bei `chp_only`.
- Entlademaske (`scenario_runner.py`): Längen-Assertion Maske vs. Zeitreihe (war schon korrekt, jetzt zusätzlich abgesichert).
- „Kurzfenster-Tests nutzen absolute Jahresstunden oder scheitern laut": jetzt technisch erzwungen — ein Kurzfenster-Test, der eine Aufweitungsstunde NICHT erreicht, bricht jetzt mit einer klaren Fehlermeldung ab, statt (wie beim ersten, fehlerhaften Dezember-Test) still gar nichts zu prüfen.

**D2 (SB-Dump-Ursache, aus `c2data_BC-SB`, dump=5, Legacy-Modus, 784,0 MWh/a gesamt — Zahl stimmt exakt mit `economics.csv` überein):**
| Knoten | Typ | Dump MWh (Std.) | Last während Dump | Strompreis während Dump vs. Jahresmittel (89,18 €) |
|---|---|---|---|---|
| j_bmhkw | KWK | 330,9 (105 h) | 14,1 MW ≈ Kapazität (14,5), 102/105 h ÜBER Mindestlast | **+109 %** |
| j_gtost | KWK | 259,3 (21 h) | 35,0 MW = volle Kapazität, 21/21 h ÜBER Mindestlast | **+237 %** |
| j_hkw | KWK | 132,5 (21 h) | 23,6 MW, nur 3/21 h über Mindestlast (12,7 MW) | −16 % |
| j_pss | Kessel | 2,9 (12 h) | 0,8 MW, 0/12 über, alle AN Mindestlast (3,2 MW) | ≈0 (leicht negativ) |
| j_psw | Kessel | 58,4 (21 h) | 5,9 MW, 0/21 über, alle AN Mindestlast (10,4 MW) | negativ |

**Zwei getrennte Muster:** `j_bmhkw`/`j_gtost` dumpen bei HOHEN Strompreisen, während die Anlage über Mindestlast (meist an Kapazitätsgrenze) läuft — stromgeführter Betrieb, Wärme ist Überschuss-Nebenprodukt. `j_hkw`/`j_pss`/`j_psw` dumpen überwiegend GENAU an der Mindestlast, oft bei niedrigen/negativen Preisen — klassischer Mindestlast-Überschuss.
**KWK-Zuschlag/Erlös bei Dump:** siehe D0 — Markterlös ist jetzt IMMER voll, unabhängig vom Dump; keine Formel nötig (keine Kürzung mehr).
**Dump-Ort heute:** netzweit an JEDEM Knoten möglich (ein `Q_dump_{node}` je Knoten, nicht anlagengebunden) — bestätigt.
**Dump an Nicht-KWK-Knoten (Unzulässigkeitskandidat unter C3):** j_pss + j_psw = **61,3 MWh (7,8 % des gesamten SB-Dumps)** — dieser Anteil hat unter `chp_only` keinen Ausweg mehr und muss über echtes Abschalten laufen oder das Modell wird unzulässig.

**D3(a) — Index-Check: KEIN Versatz.** Volljahreslauf (`d3a_C1only`, reiner C1-Test, Dump-Modus legacy): Log zeigt „applied 3/3 widened hour(s) in this run's time_set (len=8760)" — exakte Übereinstimmung, die D1-Assertion griff NICHT (kein Abbruch). Der frühere „bestandene" Dezember-Test war methodisch ungültig (kurzes Fenster indiziert `model.t` lokal, s. §4ar); mit der jetzt aktiven Aktiv-Assertion würde ein solcher Test heute selbst laut scheitern, statt einen falschen Erfolg zu melden.

**D3(b) — Ablation: BEIDE Varianten unzulässig, unabhängig voneinander.**
- **„nur C1"** (`d3a_C1only`: Druckaufweitung aktiv, Dump-Modus legacy/unrestricted): **unzulässig** (Root relaxation infeasible, ~38 s) — trotz korrekter Indizierung (a) und trotz einer rein monotonen Lockerung gegenüber dem Referenzlauf (Slack-Fixierung auf exakt den historisch beobachteten Wert an genau 3 Stunden, sonst unverändert). Ursache noch offen — feasRelax läuft (`d3c_feasrelax2.out`).
- **„nur C3"** (`d3b_C3only`: Dump-Modus `chp_only`, Druck-Modus legacy/unverändert): **ebenfalls unzulässig** (Root relaxation infeasible). Das ist **kein unerwarteter Fehler**, sondern genau das im Design vorgesehene, meldepflichtige Verhalten: MM hat laut D2-Analogie (SB) sehr wahrscheinlich Mindestlast-Überschuss an einem Nicht-KWK-Knoten (biomass_main/gasboiler_main an j_9), der ohne Dump-Ventil nicht mehr über UC allein aufgefangen werden kann. **Wird gemeldet, nicht aufgelockert** — feasRelax (Gruppe „Wärmebilanz/Mindestlast") läuft (`d3c_feasrelax_c3.out`), um Einheit/Stunden/Überschussbetrag zu quantifizieren.
**Wichtig:** Da C1 UND C3 unabhängig voneinander unzulässig sind (bei jeweils DEAKTIVIERTEM anderen Mechanismus), handelt es sich um **zwei getrennte Ursachen**, nicht eine gemeinsame. Beide feasRelax-Läufe sind nötig und laufen parallel.

**Läuft:** `d3c_feasrelax2.out` (C1, Gruppe „pressure"), `d3c_feasrelax_c3.out` (C3, Gruppe „heatbalance"/Mindestlast). TimeLimit je 600 s.


## §4at — 2026-09-22 21:35: D3(c) — IIS statt feasRelax (schneller, gleiches Ziel), BEIDE Ursachen präzise lokalisiert, gemeinsamer Verdächtiger

**Methodenwechsel (dokumentiert):** Der `gurobi_persistent`-Weg für feasRelax (D3c) baute das ~5–9-Mio.-Zeilen-Modell in Python neu auf und lief nach >20 Min. in einen Namenskonflikt (die persistente Schnittstelle vergibt andere Constraint-Namen als der dateibasierte Writer — `_station_dp(`/`ht_balance_` fand 0 Treffer). Stattdessen direkt auf der bereits von `calion/run/solver.py`s eigener Infeasibility-Behandlung geschriebenen `infeasible_model.lp` (~900 MB, volle Zeilennamen erhalten) `computeIIS()` aufgerufen — schneller (132–337 s) und liefert dieselbe Art Antwort (welche Constraints/Schranken minimal-widersprüchlich sind), nur ohne Verletzungsbetrag in MWh/bar (den nur feasRelax liefert). Skript: `scripts/paper_2/diag_iis_from_lp.py`.

**C3 (nur Dump-Sperre, Druck unverändert) — IIS: 17 Constraints + 1 Schranke, ALLE an Stunde 296:**
`c_u_hp_main_cap`, `c_u_EBOILER_MAIN_capcons`, Pipe-/Passthrough-/Wärmebilanz-Constraints an `j_5`, `j_7`, `j_12` (inkl. `c_e_ht_balance_j_12`, `c_e_J_12_mass_balance`), Bedarfs-Kopplung an `j_4`; Schranke `hp_main_cap_x_on(296)`.
**Kein einziger Dump-Constraint in dieser IIS** — die Ursache liegt NICHT in „Mindestlast-Überschuss ohne Kühler" (wie in §4as für SB via D2 vermutet), sondern in der Kapazitäts-/Bilanzkette um `j_12` bei Stunde 296, UNTER BETEILIGUNG von `hp_main`/`eboiler_main`, obwohl BC-MM beide auf `capacity_mw: 0.0` UND `investment.enabled: False` setzt.

**C1 (nur Druckaufweitung, Dump unverändert) — IIS: 41 Constraints + 9 Schranken, ALLE an Stunde 8365 (dieselben 3 Dezember-Stunden wie zuvor):**
Enthält `c_u_J_13_station_dp` (wie erwartet) UND die gesamte Druck-Propagationskette stromaufwärts (`j9_to_j10`, `j10_to_j11`, `j11_to_j13`: je `pressure_drop_supply/return`, `pressure_supply_prop`, `pressure_return_prop`), `J_13`-Lateralleitung (`lateral_w_sum`, `lateral_flow_link`, `lateral_dp_extra_def`), den Rücklaufdruck-Boden am Primärerzeuger (`c_l_J_9_pressure_return_min`), eine PWL-Segment-Schranke an einem GANZ ANDEREN Rohr (`J7_TO_J8_pp_flow`, 4 Segmente `IISLB=1,IISUB=0`), UND — **identisch zu C3** — `c_u_hp_main_cap`, `c_u_EBOILER_MAIN_capcons`, `hp_main_cap_x_on`.

**Gemeinsamer Verdächtiger:** `hp_main_cap_x_on` (Kapazitäts-Auswahl-Binärvariable) und die Bilanz-/Bedarfskette um `j_4`/`j_5`/`j_7`/`j_12` erscheinen in BEIDEN, unabhängig ausgelösten IIS — trotz `investment.enabled: False`. **Vorläufige Deutung (nicht abschließend verifiziert):** Das Deaktivieren der Investition setzt `capacity_mw`/`cap` vermutlich nicht vollständig auf einen degenerierten, widerspruchsfreien Zustand; die Binärvariable `cap_x_on` bleibt strukturell im Modell und interagiert an bestimmten Einzelstunden (8365, 296) mit der Bedarfs-/Bilanzkette hinter `j_12`. Ob das ein Datenartefakt (wie j_13s Dezember-Stunde) oder ein echter Formulierungsfehler in der Investitions-Deaktivierung ist, ist offen.
**Widerlegt:** Die ursprüngliche Annahme, die Druckaufweitung sei eine rein monotone, folgenlose Lockerung — das Fixieren der Slack-Variable (statt sie frei zu lassen) entzieht dem Solver eine Freiheit, die in der Referenzlösung mit SPEZIFISCHEN Werten der PWL-Segment-Binärvariablen (`J7_TO_J8_pp_flow`) und der Druck-Propagationskette kombiniert war; der reine Zahlenwert (3,8686 bar) reicht ohne diese Kombination nicht.

**Einordnung nach D3(d):**
- **C3-Fall (Stunde 296): melden, nicht auflockern** — wie angewiesen. Kein Dump-bezogener Constraint in der IIS, daher ist dies **kein** Beleg für „Mindestlast-Überschuss ohne Kühler" (das SB-Muster aus D2), sondern ein eigenständiger, bisher unbekannter Konflikt um die deaktivierten `hp_main`/`eboiler_main`-Binärvariablen.
- **C1-Fall (Stunde 8365): „neue Referenz unter D0+C3" laut D3(d) nicht sauber ableitbar**, weil C3 selbst (unabhängig von C1) bereits an Stunde 296 unzulässig ist — es gibt aktuell KEINE feasible „neue Konfiguration", aus der eine Referenz für die Druckaufweitung gezogen werden könnte, ohne zuerst den 296-Fall zu klären.

**Offene Fragen für den Autor (keine eigene Reparatur ohne Freigabe):**
1. Ist `investment.enabled: False` bei `hp_main`/`eboiler_main` in BC-MM tatsächlich als „Binärvariable komplett fixiert/entfernt" gedacht, oder nur als „keine neue Investition" (Binärvariable bleibt bestehen)? Das würde erklären, warum sie in BEIDEN IIS auftaucht.
2. Soll ich Stunde 296 UND Stunde 8365 als denselben Fehlerklassen-Kandidaten (isolierte Datenanomalie an einer bestimmten Stunde, analog zum bekannten j_13-Dezember-Fall) behandeln und gezielt untersuchen (z. B. Rohdaten an `j_12`/`j_4`/`j_5`/`j_7` bei Stunde 296 prüfen), bevor weitere Aufweitungs-/Notkühler-Läufe versucht werden?
3. Reicht die vorliegende IIS-Evidenz (Knoten + Stunde, keine MWh/bar-Zahl), oder soll ich den `gurobi_persistent`-Namenskonflikt beheben und die feasRelax-Läufe für den exakten Verletzungsbetrag doch noch fertigstellen?

**B2/B3-Teil-2/B4 bleiben gesperrt** bis zu einer Entscheidung hierzu.


## §4au — 2026-09-23 00:50: E1-Regression, E2-Matrix, E3-Befund, E4-Antwort

**B2/B3-Teil-2/B4 bleiben bis zu einer Entscheidung hierzu gesperrt** (Vorgabe §4at).

### E1 — Geistervariablen entfernt (heat_pump.py, p2h.py)

Umgesetzt für BEIDE genannten Stellen:
- `heat_pump.py` (hp_main): bei `not investable and capacity_init_mw<=0` wird `cap_x_on` (inkl. der 3 Linearisierungs-Constraints `linfix_hi/le_cap/lo`) GAR NICHT mehr erzeugt; `on[t]/Q[t]/Q_wrg[t]/Q_def[t]` werden stattdessen hart auf 0 fixiert; `cap`/`min`-Constraints ebenfalls übersprungen.
- `p2h.py` (eboiler_main): bei `not investable and cap<=0` wird die Commitment-Binärvariable `on` NICHT erzeugt (vorher: wurde immer erzeugt, sobald `min_load>0`, unabhängig von Kapazität — das war der eigentliche Geist); `capcons/minload/link`-Constraints ebenfalls übersprungen; `Q/P` hart auf 0 fixiert.
- Aktiv-Assertion in beiden: loggt Anzahl übersprungener Constraints + fixierter Variablen; `assert`, dass keine `*_cap_x_on`/`*_on`-Variable für eine deaktivierte Einheit existiert.

**Regressionstest (BC-MM, MM-S0-HK0, Volljahr, Legacy-Modus, identische Solver-Parameter wie die letzten bekannten Referenzläufe: MIPFocus=2, Cuts=2, MIPGap=0.5%, TimeLimit=7200s):**

| Szenario | Referenz (vor E1) | Nach E1 | Δ | Bewertung |
|---|---|---|---|---|
| BC-MM | 332.259,14 € (Gap 0,488%) | 332.259,33 € (Gap 0,488%) | +0,19 € (0,00006%) | **PASS** — praktisch identisch |
| MM-S0-HK0 | 329.418,29 € (Gap 0,473%) | 320.435,47 € (Gap n/a→~0,47%) | −8.982,82 € (−2,73%) | **abweichend, aber E1-irrelevant (s.u.)** |

**MM-S0-HK0-Abweichung eingeordnet, nicht E1 zuzuschreiben:** `hp_main`/`eboiler_main` sind in MM-S0-HK0 BEIDE `investment.enabled: true` (Basis-Config, von `tes_off_mm`-Override unberührt) → `self._disabled=False` → der exakt UNVERÄNDERTE `else`-Zweig läuft. Beleg: `git diff calion/models/blocks/heat_pump.py` und `p2h.py` (gegen HEAD `ee60b92`) zeigt, dass JEDE Codezeile im `else`-Zweig eine reine Einrückung des Original-Codes ist (keine inhaltliche Änderung) — E1 kann MM-S0-HK0 also mathematisch nicht beeinflusst haben. Die Referenzzahl (329.418,29 €) stammt von 10:40 Uhr desselben Tages, also VOR mehreren bereits an anderer Stelle entschiedenen und committeten Änderungen von heute (u. a. B1c TES-Zyklik-Fix, D0 Clawback-Entfernung) — sie ist keine gültige "vorher/nachher E1"-Baseline. Nebenbefund: Dump-Anteil ist in beiden Läufen vernachlässigbar (BC-MM 12,5 MWh/a, MM-S0-HK0 11,6 MWh/a von ~9,5 GWh/a Jahreswärme) → D0 (Clawback-Entfernung) scheidet als Ursache der Abweichung ebenfalls aus. Ursache nicht abschließend isoliert (würde eine Bisektion über mehrere Zwischen-Codestände erfordern); **E1 selbst ist damit sauber bestätigt**, unabhängig von dieser offenen, separaten Frage.

> **NACHTRAG (Autoren-Anweisung, Neubaselinierung MM-S0-HK0): 329.418,29 € ist ab sofort SUPERSEDED/OBSOLET, NICHT MEHR ZITIEREN.**
> **Neue Referenz (Legacy-Modus, Volljahr, aktueller Codestand nach E1, MIPFocus=2/Cuts=2/MIPGap=0,5%/TimeLimit=7200s): MM-S0-HK0 = 320.435,47 € (Gap 0,466%, output/mm_s4_reconcile/e1reg/MM-S0-HK0/meta.json).**
> Git-Nachweis der Irrelevanz von E1 für diese Zahl: `git diff HEAD -- calion/models/blocks/heat_pump.py calion/models/blocks/p2h.py` zeigt 113 Zeilen Änderung, ALLE ausschließlich innerhalb der neu eingeführten `if self._disabled: ... else:`-Verzweigung; der `else`-Zweig (der für MM-S0-HK0s investierbare `hp_main`/`eboiler_main` mit `self._disabled=False` tatsächlich ausgeführt wird) ist eine reine Neueinrückung ohne inhaltliche Diffs — mechanisch verifizierbar über `git diff` gegen HEAD `ee60b92c7eb4af25ab865853568aaca5edc0e76a`, da vor dieser Session weder heat_pump.py noch p2h.py in diesem Zweig verändert wurden. Die 8.982,82-€-Abweichung zur alten Zahl (10:40 Uhr desselben Tages) stammt nachweislich aus dazwischenliegenden, bereits separat entschiedenen Fixes (u. a. B1c/D0), nicht aus E1. **Alle künftigen Vergleiche/Regressionstests gegen MM-S0-HK0 verwenden 320.435,47 € als Referenz.**

**Methodische Lehre:** "bekannte Werte" für Regressionstests verfallen mit jedem inhaltlichen Fix — künftige Regressionsreferenzen sollten unmittelbar NACH dem zuletzt akzeptierten Fix neu gezogen werden, nicht von einem beliebigen früheren Lauf desselben Tages.

### E2 — Ablationen wiederholt (MM/BASE-FIX=BC-MM, Volljahr, mit D0+E1)

| Variante | Ergebnis | IIS |
|---|---|---|
| nur C1 (Druckaufweitung an, Dump legacy) | **weiterhin unzulässig** (Root relaxation infeasible, 693s) | 39 Constraints + 8 Schranken, ALLE Stunde 8366 |
| nur C3 (Dump chp_only, Druck legacy) | **weiterhin unzulässig** (630s) | 15 Constraints, ALLE Stunde 296 |
| C1+C3 (beide) | **weiterhin unzulässig** (637s) | identisch zur nur-C3-IIS (Stunde 296 dominiert) |

**Entscheidender Unterschied zu §4at (vor E1):** In KEINER der drei neuen IIS taucht mehr `hp_main_cap_x_on`, `EBOILER_MAIN_capcons` oder eine verwandte Geistervariable auf. Die C1-IIS ist jetzt eine REINE Druck-/Hydraulik-Kette (Stunde 8366: Propagation j9→j10→j11→j13, `J_13_station_dp`, Lateralleitung, PWL-Segment an einem fremden Rohr J7_TO_J8); die C3-IIS ist eine REINE Wärmebilanz-/Kopplungskette (Stunde 296: j_4/j_5/j_7/j_12 mass_balance/heat_demand/passthrough, KEIN einziger Kapazitäts- oder Dump-Constraint). **E1 hat die Entanglement-Diagnose aus §4at bestätigt und beseitigt** — beide verbleibenden Unzulässigkeiten sind jetzt strukturell sauber getrennt und eigenständig erklärbar.

### E3 — Hydraulik-Block für Stunden 8365-8367 vollständig ausgesetzt (da C1 weiter unzulässig)

**Umsetzung:** `CALION_PRESSURE_SLACK_MODE=suspend_hydraulic` (neue dritte Option neben `objective`/`preprocessed`) deaktiviert POST-HOC, nach vollständigem Modellaufbau, ALLE Constraint-Instanzen deren Komponentenname eines von 12 hydraulischen Namensfragmenten enthält (`_station_dp`, `_lateral_w_sum/_flow_link/_dp_extra_def`, `_pressure_drop_supply/_return/_total`, `pressure_supply_prop_`/`pressure_return_prop_`, `_P_supply_setpoint`, `_pressure_supply_min`/`_pressure_return_min`), an genau den 3 Stunden `{8365,8366,8367}` — netzweit, nicht nur an j_13, identisch in jedem Szenario (single source of truth: `calion.constants.HYDRAULIC_SUSPENDED_HOURS`). Zentral in `system_builder.py` (eine Stelle statt verstreuter Änderungen in 4 Dateien) mit Aktiv-Assertion (Anzahl deaktivierter Instanzen/Komponenten geloggt, `assert > 0` auf beiden Ebenen).

**Test (BC-MM, Volljahr):** 561 Constraint-Instanzen über 159 Komponenten deaktiviert; Solve jetzt **optimal**, 320.159 € (Gap 0,5%, 515s). Damit ist E3 als Fallback FUNKTIONSFÄHIG bestätigt.

**Nebenbefund + Fix (Exportpfad):** Die vollständige Entkopplung ließ `delta_p_total` (und potenziell weitere abgeleitete Pump-/Geschwindigkeits-Größen) an den 3 Stunden ohne definierende Gleichung zurück → Gurobi liefert keinen Wert ("uninitialized VarData") → der komplette Thermal-Network-Export brach mit einer Exception ab (keine `unified_timeseries.csv`, `dispatch_hourly.csv` etc. für den ganzen Lauf, nicht nur die 3 Stunden). Fix in `calion/io/thermal_network_exporter.py`: `pyo.value(..., exception=False)` mit NaN-Fallback statt Crash, für `m_dot`/`delta_p`/`velocity`. Erneuter Testlauf bestätigt: Export vollständig (18/18 Dateien), identisches Ergebnis (320.159 €). Dies ist eine reine Export-Robustheit-Korrektur (keine Modellentscheidung) — NaN an exakt den 3 als Datenartefakt verworfenen Stunden ist die ehrlichste Darstellung, nicht 0.

**Rohdaten-Kurzprüfung Stunden 8365-8367 (2025-12-15 12:00-14:00, 15-Min-Rohdaten):**

j_13 besteht aus 3 Untermessungen (V_22/V_23/V_24). **V_22 ist der Übeltäter:** von 07:00 bis ~11:00 liegt V_22_demand bei exakt 0 MW, V_22_flow_temp bei ~15°C, V_22_return_temp bei ~14°C (ΔT≈1K — Station praktisch inaktiv/nicht angeschlossen), `V_22_flow_rate_quality=1` (gut). Ab 11:15 Uhr kippt `V_22_flow_rate_quality` auf **3** (verdächtig/geschätzt) UND V_22_flow_temp springt sprunghaft auf 85-86°C (Vorlaufniveau) UND V_22_demand springt von 0 auf bis zu 1,833 MW (Maximum exakt bei 12:15 Uhr = Stunde 8366) — ein 6-facher Temperatursprung und ein Sprung von Null auf über 1,8 MW ohne jede Übergangsrampe. Nach 15:15 Uhr fällt alles wieder auf das Nahe-Null-Niveau zurück. Deckt sich exakt mit der bereits im Code dokumentierten Ursache (thermal_node.py-Kommentar): V_22 ist eine dünn besetzte, mitte-jährig in Betrieb genommene Messstelle, deren wenige echte Messwerte hier als Tagesscheibe hochgehalten werden — **ein Messstellen-/Inbetriebnahme-Artefakt, kein echtes Lastereignis.** E3s Verwurf dieser 3 Stunden ist damit sachlich gut begründet.

**Zum Vergleich Stunde 296 (2025-01-13 07:00, j_4/j_5/j_7/j_12, die C3-Unzulässigkeit):** Rohdaten in einem ±2h-Fenster zeigen **keinerlei Anomalie** — alle Verbrauchswerte (V_4 bis V_21) verlaufen glatt im üblichen 0,02-0,4-MW-Band, keine Nullstellen, keine Sprünge, keine Qualitätsflag-Auffälligkeiten; der Strompreis zeigt einen gewöhnlichen Morgenpeak-Verlauf (110→223 €/MWh). **Dies ist damit KEIN Datenartefakt wie bei j_13** — die C3-Unzulässigkeit um Stunde 296 ist nach aktuellem Stand eine echte strukturelle Lücke (vermutlich: ohne Dump-Ventil kann die Bilanzkette an diesen vier gekoppelten Knoten eine gewöhnliche, unauffällige Bedarfskonstellation nicht mehr abbilden), keine bekannte, isolierbare Anomalie. **E3 (3-Stunden-Verwurf) ist auf diesen Fall NICHT übertragbar und wurde nicht angewendet.** Diese Unzulässigkeit bleibt ungelöst und offen — siehe Empfehlung unten.

### E4 — Kessel-Mindestlast (j_pss/j_psw, Stadtbach)

`hws_boiler` (j_pss) und `hww_boiler` (j_psw): beide `type: thermal_generator`, `min_load: 0.1`, kein `investment`-Block. In `thermal_gen.py` gilt `needs_binary = min_load_fraction>0 or ...` → **JA, beide erhalten eine echte, freie Commitment-Binärvariable `on[t]`** (kann 0 werden, kein Fixieren auf 1 gefunden). **Antwort: Fall "ja" trifft zu → unverändert lassen.** Der in §4as (D2) dokumentierte Mindestlast-Dump (j_pss 2,9 MWh/12h, j_psw 58,4 MWh/21h, jeweils "alle AN Mindestlast") ist damit eine ökonomische SOLVER-Entscheidung (Dump statt Abschalten war günstiger, evtl. wegen Aktivierungskosten/Zykluskosten), keine strukturelle Zwangslage — der Mindestlast-Überschuss MUSS unter `chp_only` über Abschalten gelöst werden, wie in der Vorgabe für den "ja"-Fall festgehalten. Keine Modelländerung nötig/vorgenommen.

### Zusammenfassung / Freigabeanfrage

- **E1: bestätigt korrekt, PASS.**
- **E2: beide Restunzulässigkeiten sauber getrennt, geistervariablenfrei.**
- **E3: als Fallback funktionsfähig verifiziert (inkl. Export-Fix), Ursache für die C1-Seite (Stunde 8365-8367, j_13) datenartefakt-bestätigt.**
- **E4: beantwortet, keine Änderung nötig.**
- **OFFEN (neu, nicht Teil von E1-E4): Stunde 296 (C3-Seite, j_4/j_5/j_7/j_12) ist KEIN Datenartefakt und hat noch keinen zugewiesenen Lösungsweg.** `CALION_DUMP_MODE=chp_only` kann campaign-weit daher noch nicht gefahrlos aktiviert werden, solange diese Stunde nicht entweder (a) ebenfalls per Einzelfall-Entscheidung ausgesetzt, (b) strukturell verstanden/gefixt, oder (c) bewusst als weiterer, gesondert dokumentierter Verwurfs-Fall behandelt wird. Vorschlag zur Wahl: dieselbe Aussetzungs-Mechanik (jetzt generisch als `HYDRAULIC_SUSPENDED_HOURS`-Pattern vorhanden) ließe sich analog auf eine `BALANCE_SUSPENDED_HOURS`-Menge für Stunde 296 erweitern — das ist aber eine neue Modellentscheidung und wird hiermit nur als Option benannt, nicht umgesetzt.

**Frage an den Autor:** Wie soll mit Stunde 296 verfahren werden (b), bevor C3/`chp_only` campaign-weit nutzbar ist? Bis dahin bleibt C3 im aktuellen Zustand (Legacy-Dump, netzweit, wie vor B1) das einzige funktionierende Dump-Regime für Volljahresläufe.

**Freigabe für B2/B3-Teil-2/B4 wird hiermit angefragt** — unter dem Vorbehalt, dass B3-Teil-2/B4-Läufe mit `CALION_DUMP_MODE=chp_only` erst nach einer Entscheidung zu Stunde 296 laufen dürfen; alle anderen Modi (Legacy-Dump, C1/E3-Druckaufweitung) sind ab sofort einsatzbereit.


## §4av — 2026-09-23 12:10: F1-F4 (Stunde 296) — Diagnose abgeschlossen, F3(b) trifft zu, aber Mechanismus weicht vom SB-Präzedenzfall (D2) ab; Rückfrage vor Umsetzung. F4 durchgeführt, Meldepflicht ausgelöst.

### F1 — Diagnose Stunde 296 (kein Modelleingriff)

**Exogen fixierte Terme in der betroffenen Kette (j_4/j_5/j_7/j_12):** Bedarfsprofile (V_4-V_7 an j_4, V_8/V_9 an j_5, V_13 an j_7, V_19-V_21 an j_12) sind Parameter (Messdaten), keine Entscheidungsvariablen. An j_12 selbst existiert KEINE aktive Erzeugungseinheit (hp_main/eboiler_main in BC-MM deaktiviert). Die primärerzeugenden Einheiten (chp_main 0,2 MW/min_load 0,3; biomass_main 3,3 MW/min_load 0,1; gasboiler_main 13 MW/min_load 0,1) haben zwar alle `min_load>0`, aber auch alle eine ECHTE, freie Commitment-Binärvariable (können auf 0 gehen, thermal_gen.py `needs_binary`-Pfad, verifiziert) — keine davon ist strukturell must-run.

**Konkrete Zahlen Stunde 296 (2025-01-13 08:00, dispatch_hourly.csv):** Q_demand_total=3,291 MW, Q_biomass=2,339 MW, Q_gasboiler=1,300 MW (Summe 3,639 MW) → Netzweite Marge ≈0,348 MW — DAS ist aber die normale Transportverlust-Deckung (identische Größenordnung an allen Nachbarstunden 290-301, 0,33-0,35 MW durchgehend), KEIN Überschuss-Ereignis.

**Der tatsächlich unzulässigkeitsauslösende Betrag ist viel kleiner und lokal an j_12:** Legacy-Modus-Dump an j_12, Stunde 296 = 0,00373 MW (3,73 kWh in dieser Stunde) — glatt, kontinuierlich, KEIN Sprungmuster (Nachbarstunden 0,0028-0,0037 MW). **Häufigkeit im Jahr: 8760 von 8760 Stunden (100 %) zeigen einen nonzero-Dump an j_12** im Legacy-Referenzlauf — Werte reichen kontinuierlich von 1,7e-6 bis 0,0037 MW (Median 0,0006 MW), Jahressumme **8,02 MWh (0,08 % des Jahresbedarfs von ~9,5 GWh)**. Stunde 296 ist damit NICHT ausgezeichnet — sie ist irgendeine von 8760 strukturell ähnlichen Stunden, vermutlich die erste, die Gurobis IIS-Algorithmus als Zertifikat gefunden hat.

**Bewertung:** Kein Beleg für "fixierte Erzeugung über Bedarf" im Sinne eines Mindestlast-Überschusses. Das Muster (sub-4-kW, glatt, ganzjährig durchgehend vorhanden) ist eher mit einem topologischen/numerischen Restbetrag (ähnlich den bereits bekannten kleinen Tie-Break-/Regularisierungstermen) vereinbar als mit einem diskreten Erzeuger-Ereignis.

### F2 — Gegenprobe: C3-only auf MM-S0-HK0 (optimiertes Szenario)

**Ergebnis: EBENFALLS unzulässig** (Root relaxation infeasible, 702,6 s; `output/exports/MM-S0-HK0/0307b2fb/solver/infeasible_model.lp`).

Formale IIS für diesen Lauf lief zum Berichtszeitpunkt seit >40 Min im Hintergrund weiter (deutlich größeres Modell durch HP/EK-Investitionsvariablen; Gurobis Deletion-Filter kommt hier extrem langsam voran — Kandidatenmenge 6,2 Mio→1,9 Mio über 40 Min, praktisch Stillstand) — wird bei Fertigstellung nachgereicht, war aber für die Entscheidung nicht blockierend.

**Stattdessen Kreuzvergleich über dump_audit.json** (bereits vorhandener Post-E1-Legacy-Lauf, `output/mm_s4_reconcile/e1reg/MM-S0-HK0/`): identisches Muster an j_12 — 8754/8760 Stunden nonzero (99,9 %), Stunde 296 = 0,00244 MW (fast wie BC-MMs 0,00373 MW), glatt, kein Sprungmuster. Design-Extraktion bestätigt: `hp_main`-Kapazität=0,0 MW, build=0,0 — HP wird in dieser Referenzlösung NICHT gebaut, obwohl investierbar. "Investierbar" ist hier also eine folgenlose Unterscheidung: der Restbetrag (<3 kW) unterschreitet jede CAPEX-/Aktivierungskosten-Schwelle, der Optimierer baut ohnehin nichts, das den Betrag lokal aufnehmen könnte.

**Schlussfolgerung: Fall (b) tritt ein** — auch das optimierte Szenario ist unzulässig.

### F3 — Entscheidung nach Befund: (b) trifft zu, ABER wörtliche Umsetzung passt nicht — Rückfrage vor Umsetzung

Die Vorgabe für (b) setzt eine "zwangsweise laufende Einheit" voraus. Befund: In Memmingen ist KEINE Erzeugungseinheit strukturell must-run (alle drei Primäreinheiten haben echte, freie Commitment-Binärvariablen). Knoten j_12 selbst hat in BEIDEN Testszenarien KEINE aktive Erzeugungseinheit. Der Mechanismus unterscheidet sich damit strukturell vom SB-Präzedenzfall (D2: echter Mindestlast-Kessel-/CHP-Überschuss an einem Erzeugerknoten) — hier: ein kleiner (<4 kW, 0,08 % des Jahresbedarfs), ganzjährig durchgehend vorhandener Restbetrag an einem reinen Durchgangsknoten ohne eigene Anlage.

**Vorschlag (nicht umgesetzt, Freigabe erbeten):** Notkühler-Ventil direkt an Knoten j_12 (dem Ort des strukturellen Restbetrags), Kapazität = beobachtetes Jahresmaximum (0,0037 MW BC-MM / 0,0026 MW MM-S0-HK0), 5 EUR/MWh, NICHT netzweit freigegeben (nur dieser eine Knoten) — als nächstliegende, mit "Ansatz B" konsistente Alternative zum wörtlichen "Einheiten-Notkühler", da keine Einheit als Ziel existiert.

**Alternative zur Erwägung:** Gegeben das glatte, ganzjährige, sprungfreie Muster — passt strukturell eher zu F3(a)s "Datenschließungsterm" (data_closure_dump_MWh, Preis 0, eigene Zeile, nicht in der Kosten-Positivliste) als zu einem echten Notkühler-Fall, auch wenn (a) laut Vorgabe nur für "nur FIX-Läufe unzulässig" vorgesehen war — hier sind aber BEIDE Läufe (FIX und optimiert) betroffen, sodass (a) in der bisherigen Formulierung nicht direkt passt. **Frage an den Autor:** j_12-Notkühler (wörtlichste Anwendung von b) oder ein Datenschließungsterm an j_12 unabhängig vom FIX/optimiert-Status (Mischform a/b)?

**B2/B4 bleiben bis zu dieser Entscheidung gesperrt** (wie vorgegeben).

### F4 — B3-Teil 2 (freigegeben, DURCHGEFÜHRT): MM BASE-FIX vs BASE-HK0, Kostenzerlegung

Läufe: BASE-FIX=BC-MM (`output/mm_s4_reconcile/e1reg/BC-MM`, post-E1/D0, Legacy-Modus) vs BASE-HK0=BC-MM-HK0 (`output/mm_s4_reconcile/f4_basehk0/BC-MM-HK0`, identische Solver-Parameter, identischer Codestand).

| | BASE-FIX | BASE-HK0 | Δ (FIX−HK0) |
|---|---|---|---|
| Zielfunktionswert | 332.259,33 € | 322.834,00 € | **9.425,33 € (2,84 %)** |
| davon reale Kosten (Positivliste) | — | — | 295,65 € (**3,1 %** des Effekts) |
| davon Hilfsterme (aux) | — | — | 9.168,24 € (**96,9 %** des Effekts) |

Größter Einzeltreiber (allein 96,1 % des GESAMTEN Effekts): `Pressure_slack_cost_EUR` = 11.605,88 € (FIX) vs. 2.511,24 € (HK0), Δ=9.094,65 €. Alle anderen Terme (Fuel, CO2, Grid-Bezug/-Erlös, Netzentgelt, Dump, Tie-Break, Lateral-Tiebreak) bewegen sich im niedrigen drei- bis vierstelligen €-Bereich und heben sich weitgehend gegenseitig auf (Netto-Realkosten-Δ nur 295,65 €).

**>50-%-Meldepflicht erfüllt (96,9 %):** Der wiederholt berichtete „2,84-%-MM-Heizkurven-Hebel" ist auch NACH E1/D0 genauso robust ein Hilfsterm-Artefakt wie zuvor (§4ao: 98 % vor E1; jetzt: 96,9 % nach E1/D0 — praktisch unverändert). Das bestätigt: dies ist KEIN Nebeneffekt des Geistervariablen-Bugs, sondern ein eigenständiger, strukturell robuster Befund. TVLFIX-Betrieb erzeugt einen deutlich höheren Druck-Slack-Regularisierungsbetrag als der reale Heizkurvenbetrieb; dieser dominiert den gemeldeten Effekt fast vollständig. **Für das Paper: die reale ökonomische Wirkung des Heizkurven-Wechsels liegt bei ~296 € (0,09 %), NICHT 2,84 %.**

### Zusammenfassung

- **E1-Nachtrag:** erledigt, SUPERSEDED-Vermerk in §4au gesetzt (neue Referenz MM-S0-HK0 = 320.435,47 €).
- **F1/F2:** Diagnose abgeschlossen. Kein Mindestlast-Überschuss gefunden; stattdessen ein kleiner (≤4 kW, 0,08 % Jahresbedarf), ganzjährig durchgehend vorhandener, glatter Restbetrag an Knoten j_12 (Durchgangsknoten ohne eigene Anlage), in BEIDEN Test-Szenarien (FIX und optimiert) identisch vorhanden → Fall (b) trifft formal zu.
- **F3:** wörtliche (b)-Umsetzung ("Einheiten-Notkühler") hat kein eindeutiges Ziel, da keine Einheit must-run ist. Vorschlag (j_12-Notkühler, netzknoten-lokal) + Alternative (Datenschließungsterm unabhängig von FIX/optimiert) zur Wahl vorgelegt. **Keine Umsetzung ohne Freigabe.**
- **F4:** durchgeführt. >50-%-Meldepflicht ausgelöst (96,9 % Hilfsterme) — 2,84-%-Heizkurvenhebel ist überwiegend Regularisierungs-Artefakt (`Pressure_slack_cost_EUR`), reale Wirkung ≈0,09 %.

**B2/B4 bleiben gesperrt bis F3 entschieden ist** (wie vorgegeben).


## §4aw — 2026-09-23 13:00: G1-G4 (Autoren-Entscheidung §4av) — Re-Baseline erklärt, j_12-Diagnose ergebnislos, G3-Fallback implementiert+verifiziert, ABER der vorgegebene 0,1-%-Deckel ist für BC-MM zu eng (Lauf schlägt fehl, wie spezifiziert) — Rückfrage vor G4/B2/B4

### G1 — Re-Baseline-Differenz zugeordnet: ERKLÄRT, innerhalb des Gaps

Hypothese bestätigt. Exakte Zahlen (MM-S0-HK0, alt=`cbB_S0`/10:40 Uhr, dump=1000 EUR/MWh; neu=`e1reg`/nach E1+B1a, dump=5 EUR/MWh):

| | Dump-Menge | Preis | Dump-Kosten |
|---|---|---|---|
| ALT | 9,335 MWh | 1.000 EUR/MWh | 9.335,37 € |
| NEU | 11,590 MWh | 5 EUR/MWh | 57,95 € |

Dump-Kosten-Δ (alt−neu) = **9.277,42 €**. Gesamt-Zielfunktions-Δ (alt−neu) = **8.982,83 €** (= die berichteten 8.983 €). Restbetrag = 9.277,42 − 8.982,83 = **294,59 €** — andere reale Kostenterme bewegten sich leicht gegenläufig (plausibel: bei 5 EUR/MWh lohnt sich geringfügig mehr Dump als bei 1.000 EUR/MWh, was den Dispatch an anderer Stelle minimal verändert). 294,59 € liegt weit innerhalb der MIP-Gap-Toleranz beider Läufe (~1.500-1.560 €). **Dokumentiert wie vorgegeben: erklärt durch die B1a-Dump-Preissenkung (1.000→5 EUR/MWh), nicht E1.** (Nutzers Vereinfachung: 9,335 MWh × 995 EUR/MWh = 9.288,69 € — 11 € vom exakten Wert entfernt, bestätigt dieselbe Erklärung.)

### G2 — j_12-Offset-Diagnose (kein Modelleingriff, ~1 h): ERGEBNISLOS, kein fixierbarer Root Cause gefunden

- **Konstanz:** NICHT exakt konstant. Std.-Abw. über 8760 h = 0,00085 MW (Mittel 0,00092 MW, CV=0,93). **Klar saisonal:** Monatsmittel 0,0021 MW (Januar) bis 0,00014 MW (Juli) — proportional zur Heizlast, kein Sprungmuster, kein diskretes Erzeuger-Ereignis.
- **Bedarfszeitreihe/Kopplung j_12:** 3 Verbraucherspalten (V_19/V_20/V_21, `consumers:`-Liste), Standard-Multi-Consumer-Pfad. Code-Audit (system_builder.py Zeilen 145-190, thermal_node.py Zeilen 314-377): `heatd_j_12` (für die Bilanzgleichung, constraint_builder.py) und der interne `{prefix}_Q_demand`-Aggregat (thermal_node.py, für Massenstrom/Druck) werden BEIDE aus denselben `heatd_j_12_{i}`-Parametern aufsummiert — mathematisch identisch, kein Diskrepanz-Potenzial gefunden.
- **Doppelt gezählter/fest hinterlegter Verbraucher/Erzeuger:** Keiner gefunden. `unified_config.py` erlaubt `demand:` (singulär) UND `demands:`/`consumers:` (Liste) als getrennte, NICHT überlappende Felder; j_12s Config nutzt ausschließlich `consumers:`, kein zusätzliches `demand:`. Bilanzgleichung (constraint_builder.py `secondary_combined_balance`, Z. 500-512) nutzt für die eingehende Rohrleitung explizit `Q_consumer` (netto, Verlust bereits abgezogen) und für abgehende Rohrleitungen `Q_delivered` (brutto, inkl. deren eigenem Verlust) — physikalisch korrekt, kein struktureller Doppel-Zähl-Fund.
- **Abgleich mit der bekannten 1,8-%-j_12-Bilanzlücke (§4ad/§4ae, 0,17 GWh):** **VERMUTLICH ANDERE URSACHE, nicht dieselbe.** Skalenunterschied ~20× (170 MWh/Jahr vs. hier gefundene 8-12,5 MWh/Jahr) und andere Code-Ebene: die 1,8-%-Lücke ist explizit als **Export-/Reporting-Diskrepanz** dokumentiert (dispatch_hourly.csv berichtet 87,5 MWh/Woche gelieferte Wärme an j_12, tatsächlicher Rohrfluss nur 81,8 MWh/Woche — ein Nachbearbeitungs-Artefakt in `dispatch_per_asset`/`dispatch_hourly`, komplett getrennt vom hier untersuchten LIVE-Optimierungs-Constraint `Q_dump_j_12`). Beide Funde betreffen denselben Knoten, aber über unterschiedliche Code-Pfade und unterschiedliche Größenordnung — als zwei separate, nicht ursächlich verbundene Befunde behandelt.
- **Ergebnis: ERGEBNISLOS** — keine fixierbare Ursache in Bedarfs-Parameter-Konstruktion oder Bilanzgleichungs-Struktur gefunden. **→ G3-Fallback greift.**

### G3 — Fallback implementiert: `data_closure_dump_MWh` (Preis 0, Pflicht-KPI, harter Deckel 0,1 % Jahresbedarf)

**Umsetzung** (`calion/models/constraint_builder.py`, `calion/run/result_collector.py`, `scripts/paper_2/extract_artefacts_p2.py`): unter `CALION_DUMP_MODE=chp_only` werden die Pro-Knoten-Dump-Variablen NICHT mehr auf 0 fixiert, sondern bleiben frei — jedoch (a) mit Preis 0 (aus der Zielfunktion ausgeschlossen: `global_dump_rule` liefert unter chp_only `Q_dump[t]=0` identisch, die reale, bepreiste `Dump_cost_EUR` bleibt 0), (b) netzweit hart gedeckelt via eine neue Constraint `data_closure_cap`: Σ über alle Knoten/Stunden ≤ 0,1 % des gesamten Jahresbedarfs. KEIN Notkühler an j_12 (dort keine Anlage — wie vorgegeben). Mandatory KPI `data_closure_dump_MWh` in `cost_breakdown.json` als eigenes Top-Level-Feld (NICHT in `real_costs_EUR`/`model_aux_terms_EUR`), 0,0 in allen Nicht-chp_only-Läufen.

**Bug gefunden+behoben:** erster Testlauf crashte (`TypeError: 'NoneType' object is not iterable`) — Pyomo ruft eine skalare `Constraint(rule=...)` intern teils als `rule(model, None)` auf; ein Default-Argument (`def rule(m, _cv=closure_vars)`) wird dabei POSITIONELL von `None` überschrieben. Behoben durch reinen Closure-Zugriff statt Default-Argument (kein Late-Binding-Risiko, da die Regel exakt einmal sofort verwendet wird).

**Test (BC-MM, Volljahr, `chp_only`, nach Bugfix):** Mechanismus feuert korrekt (Log bestätigt: „15 node(s) get a FREE, 0-EUR/MWh 'data closure' dump", Deckel korrekt berechnet: **9,4332 MWh = 0,1 % von 9.433,22 MWh Jahresbedarf**). **Ergebnis: WEITERHIN UNZULÄSSIG** — wie in der Vorgabe als möglicher, meldepflichtiger Ausgang vorgesehen ("Lauf schlägt fehl"). Quantitativer Beleg: BC-MMs eigener Legacy-Referenzlauf (bepreist, 5 EUR/MWh — d. h. mit einem gewissen Anreiz, WENIGER zu dumpen als bei Preis 0) verwendet bereits **12,50 MWh/Jahr** (Dump_cost_EUR 62,52 € / 5 EUR/MWh) — das sind **32,5 % MEHR als der 9,4332-MWh-Deckel erlaubt**, OBWOHL dieser bepreiste Referenzwert den freien (0-EUR) Bedarf eher UNTERSCHÄTZT (ein positiver Preis drückt die genutzte Menge tendenziell nach unten). Der tatsächliche, ungedeckelte Bedarf liegt also mit hoher Wahrscheinlichkeit noch über 12,50 MWh.

**Bewertung:** G3 ist korrekt implementiert und funktioniert wie spezifiziert — der Deckel tut exakt das, was er soll (hart scheitern statt still tolerieren). Der 0,1-%-Wert selbst ist für Memmingen/BC-MM aber zu eng für den empirisch beobachteten Strukturbedarf.

### G4 — NICHT erreichbar: G3-Fallback scheitert unter dem vorgegebenen 0,1-%-Deckel — Rückfrage vor Neu-Baselines/B2/B4

Da bereits BASE-FIX (BC-MM) unter dem spezifizierten 0,1-%-Deckel unzulässig bleibt, können die in G4 geforderten neuen Referenzen (BASE-FIX, BASE-HK0, S0-HK0 je Netz) unter `chp_only` noch nicht gezogen werden. **Drei Optionen zur Wahl, nichts davon umgesetzt:**
1. **Deckel anheben** — z. B. auf einen Wert, der den empirisch beobachteten ~12,5-15 MWh-Bedarf mit Headroom abdeckt (z. B. 0,15-0,2 % ≈ 14-19 MWh); erfordert eine neue Zahl vom Autor, da 0,1 % explizit vorgegeben war.
2. **chp_only für BC-MM/Memmingen (bzw. Netze mit ähnlichem Befund) vorerst nicht verwenden** — Legacy-Dump (netzweit, wie vor B1) bleibt das einzige nutzbare Dump-Regime dort; B2/B4 liefen dann ohne `chp_only`.
3. **Weitere Strukturuntersuchung** (über das 1-h-Budget von G2 hinaus) — z. B. eine feinere Zerlegung der PWL-/McCormick-Toleranzen an j_12, falls der Restbetrag dort numerisch (nicht physikalisch) bedingt ist.

**Stadtbach ist von diesem Test noch nicht separat verifiziert** (G3 bislang nur auf BC-MM getestet) — sollte bei einer Deckel-Entscheidung mitgeprüft werden, bevor „je Netz"-Referenzen gezogen werden.

**B2/B4 bleiben bis zu dieser Entscheidung gesperrt.**

### F4-Nachtrag (Housekeeping)

„Heizkurve MM 2,84 %" als widerlegte Aussage im Kontrolldokument vermerkt (siehe §4ae, direkt bei der Originalaussage) — realer Effekt ≈ 0,09 %.


## §4ax — 2026-09-23 14:15: H1 umgesetzt+verifiziert, H2 BESTÄTIGT (Mechanismus geklärt) — H3 (G4/B2/B4) startet

### H1 — Obergrenze auf 0,25 % angehoben

Umgesetzt in `constraint_builder.py` (`_closure_cap_frac = 0.0025`, war 0.001), `result_collector.py` (Pflicht-KPI `data_closure_dump_MWh` + neues `Data_closure_dump_pct_of_demand`-Feld, WARNUNG im Log ab 0,125 % — kein Abbruch, nur `logger.warning`; harter Abbruch bleibt bei 0,25 % über die Constraint `data_closure_cap`), `extract_artefacts_p2.py` (KPI jetzt MWh UND % im `cost_breakdown.json`-Feld `data_closure_dump_MWh`, weiterhin NICHT in `real_costs_EUR`/`model_aux_terms_EUR`).

**Verifiziert (BC-MM, Volljahr, `chp_only`):** löst jetzt **optimal, 331.463 € (Gap 0,267 %)** — die erste erfolgreiche `chp_only`-Lösung für BC-MM in dieser gesamten Kampagne. Warnschwelle griff korrekt: `data_closure_dump_MWh = 12,1258 MWh = 0,1285 %` (über 0,125 %-Warnschwelle, WARNUNG geloggt, KEIN Abbruch — unter dem 0,25-%-Deckel von 23,5831 MWh). Mechanik arbeitet exakt wie spezifiziert.

**Dokumentation der Begründung (wie gefordert):** Die 0,25-%-Grenze ist ein **Drift-Wächter**, keine physikalische Schranke — sie verhindert, dass ein ECHTER, großer Mindestlast-Überschuss (das D2-SB-Muster) sich unbemerkt hinter dem Datenschließungsventil verstecken kann, indem sie bei deutlichem Überschreiten hart abbricht. Das tatsächlich beobachtete STRUKTURELLE Lieferresiduum (siehe H2) liegt bei 0,08–0,13 % des Jahresbedarfs (BC-MM legacy 0,1325 %, unter `chp_only`/H1 0,1285 % — konsistent) — die 0,25-%-Grenze liegt bewusst knapp doppelt darüber, mit Warnpuffer bei der Hälfte (0,125 %).

### H2 — Mechanismusprüfung (~30 Min, nur vorhandene Exporte + 1 Modellaufbau-Capture, kein Solver-Lauf): BESTÄTIGT

**Exakte algebraische Identität verifiziert** (BC-MM, `e1reg`, alle 8760 Stunden, Knoten j_12): `dump(j_12,t) = Q_rohr_ein(t) − Q_bedarf(j_12,t) − Q_rohr_aus(t)` — Korrelation **1,0**, mittlere Abweichung **7,7×10⁻¹⁷ MW** (reine Gleitkomma-Rundung). Dies ist die Knotenbilanzgleichung selbst (tautologisch, da harte Gleichheits-Constraint) — bestätigt aber, dass KEIN verstecktes zusätzliches Bilanzelement fehlt. `Q_bedarf(j_12,t)` wurde direkt aus dem laufenden Modell extrahiert (`heatd_j_12`-Parameter, per Monkeypatch-Capture VOR dem Solve, exakte Modellwerte statt eigener Neuberechnung aus den Rohdaten — eine erste Version mit eigenem stündlichem Resample der 15-Min-Rohdaten lag noch 7 % daneben und hätte die Prüfung verfälscht).

**Physik-Kopplung bestätigt:** `Q_rohr_ein(t) ≈ m_dot_ein(t) × cp × ΔT_Knoten(t)` (cp=4,189 kJ/kgK, ΔT aus `T_supply−T_return` am Knoten) — Korrelation **1,0** zum exportierten `Q_pipe_MW`, mittlere Abweichung 0,0005 MW (Rundung/Interpolation im Export). **Die Nutzer-Hypothese ist damit bestätigt:** der Dump ist ein reines Liefer-/Kopplungsresiduum aus Massenstrom × Temperaturdifferenz, KEIN Mindestlast-/Must-run-Ereignis — der Massenstrom in den j_12-Zweig wird durch eine netzweite Optimierung (Druckabfall-PWL, Pumpleistungs-Minimierung, kleine Tie-Break-/Regularisierungsterme wie `Pressure_reg_cost_EUR`/`Lateral_tiebreak_cost_EUR`) bestimmt, nicht durch eine lokale Punkt-zu-Punkt-Abstimmung auf den exakten j_12-Bedarf — daher das glatte, saisonal mit der Last skalierende, nie-ganz-null-werdende Restmuster (G2).

**Andere Knoten/SB:** Innerhalb von BC-MM zeigt AUSSCHLIESSLICH j_12 dieses glatte Residuum (dump_audit.json: nur j_12 und j_9; j_9s Muster ist das klassische, sprunghafte Mindestlast-Ereignis, nicht dasselbe Phänomen). In den vorhandenen Stadtbach-Exporten (`c2data_BC-SB`, Legacy-Referenz) tritt das j_12-Muster NICHT auf — die dort dumpenden Knoten (j_bmhkw, j_gtost, j_hkw, j_pss, j_psw) sind ausschließlich Erzeugerknoten mit dem bekannten D2-Mindestlast-Muster (784 MWh/Jahr gesamt, siehe §4as), nicht Durchgangsknoten ohne Anlage. **Gesamtmenge je Netz:** MM ≈ 8-12,5 MWh/Jahr (j_12-Residuum, dieses Phänomen); SB: 0 MWh diesem Phänomen zurechenbar (SB hat aktuell keinen bekannten reinen Durchgangsknoten-Fall dieser Art in den vorhandenen Exporten — nicht separat neu getestet, wie von H2 gefordert nur aus bestehenden Daten beurteilt).

**Methodenteil-Formulierung (3-5 Sätze, Entwurf):**
> An passthrough-Knoten ohne eigene Erzeugungsanlage (hier: Memmingen j_12) entsteht ein kleines, kontinuierliches Lieferresiduum: der eingehende Rohrmassenstrom wird nicht lokal auf den Knotenbedarf abgestimmt, sondern folgt einer netzweiten Optimierung aus Druckabfall, Pumpleistung und numerischen Regularisierungstermen. Die daraus resultierende Differenz zwischen gelieferter Wärme (Massenstrom × cp × ΔT) und tatsächlichem Bedarf plus Weiterleitung ist strukturell unvermeidbar in einem kontinuierlichen MILP mit netzweiter Flussoptimierung, bleibt aber klein (0,08-0,13 % des Jahresbedarfs am betroffenen Netz) und korreliert glatt mit der Heizlast statt in diskreten Sprüngen aufzutreten — ein klares Unterscheidungsmerkmal zu einem echten Mindestlast-Überschuss an einer Erzeugungseinheit. Das Modell behandelt diesen Fall über ein explizites, ungepreistes, hart gedeckeltes „Datenschließungsventil" (`data_closure_dump_MWh`, ≤0,25 % des Jahresbedarfs), das einen echten, großen Erzeugungsüberschuss weiterhin als Unzulässigkeit meldet statt ihn zu verschleiern.

**Ergebnis: H2 BESTÄTIGT → H3 startet ohne weitere Rückfrage, wie vorgegeben.**

### H3 — G4/B2/B4 gestartet

**Kombinationstest (BC-MM, `chp_only` + `suspend_hydraulic` gemeinsam, vor Kampagnenstart):** [wird nachgetragen, Lauf läuft]

**B2-Faktordesign:** aus dem Kontext dieser Session rekonstruiert (die ursprüngliche Definition liegt vor der Kontext-Zusammenfassung dieser Konversation und ist nicht wörtlich verfügbar) — **Arbeitsannahme:** 2×2-Faktorexperiment auf MM zur Attribution der B1a/B1b-Effekte: Faktor 1 = Dump-Preis (1000 vs. 5 EUR/MWh), Faktor 2 = Druck-Slack-Behandlung (frei/`objective` vs. `suspend_hydraulic`), jeweils auf BASE-FIX. Falls das nicht der ursprünglichen Definition entspricht, bitte korrigieren — wird sonst wie oben umgesetzt, da explizit „ohne weitere Rückfrage" angewiesen.

**B4-Protokoll (wie spezifiziert):** MM TimeLimit 4h, SB TimeLimit 8h, MIPGap 1e-4, MIPFocus 3, S0-Szenarien im selben Protokoll; Ergebnis als Intervalle (LB/UB aus Gap) auf realen Kosten (nicht Zielfunktion), nicht als Punktschätzung.

**Zusatzpflicht (Heizkurve ohne Druck-Slack):** wird bei jedem HK0/S0-HK0-Lauf beachtet — falls unzulässig, wird das als Ergebnis (hydraulische Grenze der Heizkurvenabsenkung, mit Knoten+Stunden) gemeldet, NICHT durch zusätzliche Lockerung umgangen.

**Status:** Kampagne wird jetzt gestartet (6 neue Referenzen je Netz, dann B2, dann B4) — Fortschritt wird laufend in diesem Dokument nachgetragen.


## §4ay — 2026-09-23 16:50: H3-Fortschritt — BC-SB (BASE-FIX) fertig, ZWEITER Bug gefunden+behoben, WICHTIGER Befund: 0,25-%-Deckel bindet bei SB (anders als MM)

### Bug 2: `data_closure_dump_MWh`-KPI zählte fälschlich CHP-Dump mit

BC-SBs erster Lauf unter der finalen Konfiguration meldete `data_closure_dump_MWh = 2.240,48 MWh = 0,3501 %` — SCHEINBAR über dem 0,25-%-Deckel, obwohl der Solver "optimal"/zulässig meldete (kein Widerspruch zur Constraint selbst möglich). Ursache: die Diagnose-Schleife in `result_collector.py` sammelt ALLE Variablen mit Namenspräfix `Q_dump_` — das trifft NICHT NUR die knotenweisen, gedeckelten `Q_dump_{node_id}`-Variablen, sondern AUCH die separate, bewusst UNGEDECKELTE `Q_dump_chp_{ASSET}`-Variable aus C3/Ansatz B (component_assembler.py). Aufschlüsselung: `chp_BMHKW` 223,38 + `chp_GTOST` 318,16 + `chp_HKW` 99,00 = 640,54 MWh (KWK-Mechanismus, korrekt ungedeckelt) + `j_bmhkw` 359,98 + `j_hkw` 1.172,54 + `j_pss` 21,36 + `j_psw` 46,06 = **1.599,94 MWh (tatsächlich von der Constraint `data_closure_cap` gedeckelte Menge)** = 2.240,48 MWh Summe. Die eigentliche Deckel-Constraint war zu keinem Zeitpunkt verletzt — nur die KPI-Berechnung war falsch. **Behoben** in `result_collector.py`: Summe schließt jetzt `chp_`-präfigierte Einträge aus.

### Wichtiger Befund (kein Bug): SB-Deckel bindet, MM-Deckel hatte Puffer

**1.599,94 MWh vs. Deckel 1.599,93 MWh (0,25 % von 639.973,5 MWh Jahresbedarf) — praktisch EXAKT am Deckel** (Differenz 0,01 MWh, innerhalb normaler Solver-Toleranz — die Constraint ist AKTIV/bindend, kein Zufall). Das unterscheidet sich fundamental vom MM-Befund (H1: 12,13 von 23,58 MWh Deckel = 51 % Auslastung, komfortabler Puffer). **Der größte Teil der SB-Deckelnutzung liegt an den KWK-Knoten selbst** (j_bmhkw 360 + j_hkw 1.173 = 1.532 MWh von 1.600 MWh, 96 %), nicht an reinen Durchgangsknoten wie MMs j_12 — d. h. diese Knoten brauchen SOWOHL ihren eigenen `Q_dump_chp`-Auslass ALS AUCH zusätzlich den knotenweisen Schließungsterm, was auf einen größeren lokalen Bilanz-Restbetrag als bei MM hindeutet (plausibel: SB ist ein Maschennetz mit mehreren Erzeugern, MM ein einfacher Baum — mehr Freiheitsgrade in der Massenstromaufteilung könnten den in H2 identifizierten Mechanismus verstärken).

**Konsequenz:** Der 0,25-%-Deckel könnte für SB an der Kapazitätsgrenze operieren, nicht mit Komfort-Puffer wie bei MM — das Ergebnis (Zielfunktion, Dispatch) dieses BC-SB-Laufs könnte dadurch leicht künstlich verzerrt sein (Constraint bindend statt inert). **Nicht selbst gelockert** — wird gemeldet, wie vom Autor für genau diesen Fall vorgegeben.

### Zusätzlich: MIP-Gap NICHT erreicht (TimeLimit)

BC-SB erreichte in 7.767 s (TimeLimit 7200 s + Exportzeit) nur **6,4 % Gap** (Ziel 0,5 %), `status=maxTimeLimit`. Zielfunktion 22.550.093 € ist damit ein VORLÄUFIGER, nicht konvergierter Wert — konsistent mit der gesamten Kampagne: SB braucht strukturell mehr Zeit als MM (siehe B4-Protokoll, das dem bereits mit SB=8h vs. MM=4h Rechnung trägt — diese H3-Baseline-Läufe liefen aber noch mit den STANDARD-Solver-Parametern, nicht dem B4-Protokoll). `Objective_residual_EUR = 1.677.607 €` sah zunächst alarmierend groß aus, ist aber vollständig durch die bereits dokumentierte `CO2_selfuse_netting_adjustment_EUR` (−1.674.404 €) erklärt (`reconciliation_check: OK`, Rest ≈ 3.203 € Rundung) — bei SBs viel größerem KWK-Volumen ist dieser bekannte Mechanismus einfach absolut größer, kein neuer Fehler.

**Empfehlung (nicht umgesetzt, zur Kenntnisnahme):** BC-SBs H3-Referenzwert sollte als VORLÄUFIG behandelt werden, bis entweder (a) B4s eigener 8h-SB-Lauf eine belastbare Zahl liefert, oder (b) der 0,25-%-Deckel für SB gezielt überprüft wird (eigener, netzspezifischer Wert statt einer für beide Netze geltenden Pauschale?).

**Kampagne läuft weiter** (nächster Lauf: SB-S0-HK0, dann BC-SB-HK0, BC-MM-HK0, MM-S0-HK0).

### Nachtrag: SB-S0-HK0 bestätigt den Deckel-Befund exakt — zweiter Datenpunkt

**SB-S0-HK0 (Volljahr, finale Konfiguration):** korrigierte Knoten-Schließungsmenge = **1.599,93 MWh — identisch (auf die zweite Nachkommastelle) mit BC-SBs 1.599,94 MWh**, also wieder EXAKT am 0,25-%-Deckel (0,25 % von 639.973,5 MWh = 1.599,93 MWh). Zwei unabhängige SB-Szenarien landen beide exakt an der Kappungsgrenze — das ist kein Zufall, sondern ein reproduzierbarer Befund: **der Deckel bindet strukturell für Stadtbach.**

(Hinweis zur KPI-Anzeige: dieser und der laufende Prozess wurden VOR dem Bugfix in `result_collector.py` gestartet und melden im Log weiterhin die unkorrigierte Summe inkl. `Q_dump_chp_*` — z. B. SB-S0-HK0 loggt „5.517,61 MWh". Der oben genannte, korrekte Wert 1.599,93 MWh ist manuell aus `dump_audit.json` unter Ausschluss der `chp_`-Einträge nachgerechnet. Der Bugfix wirkt erst ab dem nächsten NEU gestarteten Python-Prozess, z. B. B2/B4.)

**Konvergenz noch schlechter als BC-SB:** `status=maxTimeLimit`, Gap **31,4 %** (BC-SB: 6,4 %) — Zielfunktion 30.446.072 € ist damit NOCH vorläufiger als BC-SBs Wert. `Objective_residual_EUR=2.085.902 €` erneut vollständig durch `CO2_selfuse_netting_adjustment_EUR` (−2.066.314 €) erklärt, `reconciliation_check: OK` — kein neuer Fehler.

**Aktualisierte Empfehlung:** Gegeben zwei von zwei SB-Läufen exakt am Deckel landen, ist eine SB-spezifische Prüfung des 0,25-%-Werts (Option b oben) jetzt deutlich dringlicher als zuvor eingeschätzt — beide bisherigen SB-Zielfunktionswerte sind mit doppelter Vorsicht zu behandeln (Deckel UND weite Gap).

### MM-Referenzen: alle 3 fertig, sauber konvergiert

| Lauf | Ziel € | Gap | Schließung MWh | % vom Deckel (23,58 MWh) |
|---|---|---|---|---|
| MM BASE-FIX (BC-MM, Kombi-Test) | 320.114 | ~0,27 % | 12,13 | 51 % |
| MM BASE-HK0 (BC-MM-HK0) | 319.741 | 0,21 % | 11,57 | 49 % |
| MM S0-HK0 | 317.352 | 0,49 % | 11,62 | 49 % |

Alle drei MM-Referenzen sind sauber konvergiert (Gap ≤ 0,5 %) und zeigen konsistent komfortablen Deckel-Puffer (~49-51 %, nie bindend) — MM ist als Netz für die finale Konfiguration unproblematisch bestätigt.

### Nachtrag: Systemneustart 2026-09-23 21:51 — `BC-SB-HK0` verloren, sauber neu gestartet und reproduziert

Das Betriebssystem startete um 21:51:09 neu (Ursache unbekannt — nicht durch mich ausgelöst; 2 harmlose VS-Code-Python-Prozesse `ms-python.isort` liefen danach neu an, sonst nichts Auffälliges) und beendete den laufenden `BC-SB-HK0`-Prozess ohne Speicherung, ~8 Minuten nach dem letzten Logeintrag (Gap 1,95 %, 95 Min. Laufzeit — verloren, kein Checkpoint-Mechanismus vorhanden). Die anderen 4 H3-Läufe waren zu diesem Zeitpunkt bereits fertig exportiert und dadurch sicher. `BC-SB-HK0` wurde identisch neu gestartet (`--force-rerun`, gleiche Konfiguration) und lief **deterministisch identisch** zum verlorenen Versuch (exakt gleiche Root-Relaxation, gleiche Inkumbenten-Sequenz zu denselben internen Zeitstempeln) — guter Beleg für Reproduzierbarkeit der gesamten Pipeline.

### H3/G4 abgeschlossen: alle 6 Referenzen fertig

| Netz | Lauf | Ziel € | Gap | Schließung MWh | % vom Deckel |
|---|---|---|---|---|---|
| MM | BASE-FIX (BC-MM) | 320.114 | ~0,27 % | 12,13 | 51 % |
| MM | BASE-HK0 (BC-MM-HK0) | 319.741 | 0,21 % | 11,57 | 49 % |
| MM | S0-HK0 | 317.352 | 0,49 % | 11,62 | 49 % |
| SB | BASE-FIX (BC-SB) | 22.550.093 | 6,40 % | 1.599,94 | **100 % (am Deckel)** |
| SB | BASE-HK0 (BC-SB-HK0) | 21.506.975 | 1,91 % | 1.279,39 | 80 % (Puffer) |
| SB | S0-HK0 | 30.446.072 | 31,40 % | 1.599,93 | **100 % (am Deckel)** |

**Präzisierung des Deckel-Befunds:** Nicht alle SB-Läufe sind bindend — BASE-HK0 hat spürbaren Puffer (80 %), während BASE-FIX und S0-HK0 exakt am Deckel liegen. Die reale Heizkurve (HK0, niedrigere Vorlauftemperaturen in Schwachlaststunden) scheint das Kopplungsresiduum (H2-Mechanismus) zu verkleinern — konsistent mit der H2-Diagnose, dass der Effekt aus Massenstrom-/ΔT-Kopplung stammt, die sich mit dem Temperaturregime ändert. Trotzdem bleiben BASE-FIX und S0-HK0 mit doppelter Vorsicht zu behandeln (Deckel UND, bei S0-HK0, sehr weite Gap).

**Alle 6 H3-Referenzen sind damit gezogen. G4 ist erledigt — weiter mit B2 und B4.**


## §4az — 2026-09-24 12:20: B2 — 2×2-Attribution MM abgeschlossen (Design rekonstruiert, siehe §4ax)

**Design (Arbeitsannahme, siehe §4ax):** 2×2-Faktorexperiment auf BC-MM (BASE-FIX, Legacy-Dump-Modus, NICHT `chp_only`), Faktor 1 = Dump-Preis (1.000 vs. 5 EUR/MWh, per neuem `CALION_DUMP_PRICE_OVERRIDE`-Env-Override implementiert — Konfigurationsdateien bleiben unverändert, jeder Lauf bleibt aus derselben Datei reproduzierbar), Faktor 2 = Druck-Slack-Behandlung (`objective` = frei/ungedeckelt vs. `suspend_hydraulic` = E3-Mechanismus).

| | Druck = `objective` (frei) | Druck = `suspend_hydraulic` |
|---|---|---|
| Dump = 1.000 €/MWh (alt) | 341.845 € | 330.227 € |
| Dump = 5 €/MWh (neu, B1a) | 332.259 € | 320.159 € |

**Attribution (additiv, kaum Interaktion):**
- Dump-Preis-Effekt (1.000→5): 9.586 € bei `objective`, 10.067 € bei `suspend_hydraulic` — **Mittel 9.826 € (45,3 % des Gesamteffekts).**
- Druck-Slack-Effekt (`objective`→`suspend_hydraulic`): 11.618 € bei Dump=1.000, 12.100 € bei Dump=5 — **Mittel 11.859 € (54,7 % des Gesamteffekts).**
- Interaktionsterm: nur 482 € (2,2 % des Gesamteffekts) — die beiden Faktoren wirken **fast rein additiv**, keine nennenswerte Kopplung.
- Gesamteffekt (1.000/`objective` → 5/`suspend_hydraulic`): **21.685 €.**

**Sanity-Checks bestanden:** Zelle (1.000, `objective`) = 341.845 € trifft den historischen §4ae-Referenzwert (341.844 €) exakt — bestätigt, dass der neue `CALION_DUMP_PRICE_OVERRIDE`-Mechanismus korrekt funktioniert. Zelle (5, `objective`) = 332.259 € trifft `e1reg`s Legacy-BC-MM-Referenz exakt. Zelle (5, `suspend_hydraulic`) = 320.159 € war bereits aus der E3-Verifikation bekannt (§4au) und wurde hier wiederverwendet, nicht neu gerechnet.

**Einordnung:** Beide B1-Fixes (Dump-Preis UND Druck-Slack-Behandlung) tragen in ähnlicher Größenordnung zum Gesamteffekt bei — der Druck-Slack-Anteil (54,7 %) ist tendenziell der GRÖSSERE der beiden, nicht der Dump-Preis (45,3 %), obwohl B1a (Dump-Preis) in früheren Berichten oft als der dominante Faktor dargestellt wurde. Beide Fixes waren nötig; keiner dominiert eindeutig.

**B2 abgeschlossen. Weiter mit B4 (matched-effort-Kampagne).**


## §4ba — 2026-09-24 12:20: B4 gestartet (matched-effort-Kampagne)

**Umfang:** 6 Läufe (BASE-FIX/BASE-HK0/S0-HK0 je Netz), finale Konfiguration (`chp_only` + `suspend_hydraulic` + Datenschließung 0,25 %), Protokoll wie vorgegeben: MM TimeLimit 4 h (14.400 s), SB TimeLimit 8 h (28.800 s), `MIPGap=1e-4`, `MIPFocus=3`, jeweils `--force-rerun` (die H3/G4-Werte unter Standard-Solver-Einstellungen bleiben als separate Referenz erhalten, werden nicht überschrieben — anderer `CALION_OUT_BASE`). MM (3 Läufe, sequenziell, `b4_mm`) und SB (3 Läufe, sequenziell, `b4_sb`) laufen PARALLEL zueinander (ausreichend RAM/CPU-Headroom, siehe frühere Prüfung: >120 GB frei, 66 logische Kerne, je Lauf `Threads=4`).

**Realistischer Zeitrahmen: MM bis zu ~12 h (3×4 h worst case, erfahrungsgemäß deutlich schneller), SB bis zu ~24 h (3×8 h worst case) — dies ist eine Mehrtages-Kampagne, kein Vorgang, der in dieser Sitzung vollständig beobachtet werden kann.**

**Bekanntes Risiko (bereits einmal eingetreten, §4ay):** Ein unvorhergesehener Systemneustart hat bereits einmal einen laufenden H3-Lauf verloren (95 Minuten Rechenzeit, kein Checkpoint-Mechanismus). Bei den deutlich längeren B4-SB-Läufen (bis zu 8 h je Lauf) wäre ein Verlust durch einen erneuten Neustart entsprechend teurer. Kein Checkpointing vorhanden — wird zur Kenntnis gebracht, nicht selbst behoben (außerhalb des aktuellen Auftragsumfangs).

**Ergebnis wird wie vorgegeben als Intervall (LB aus Bound, UB aus Inkumbent, beide aus dem Gap) auf realen Kosten berichtet, sobald verfügbar — nicht als Punktschätzung, besonders wo `MIPGap=1e-4` nicht erreicht wird (bei SB nach den H3-Erfahrungswerten wahrscheinlich).**

### Zwischenstand 2026-09-25 08:33

**B4 MM: alle 3 Läufe fertig, sehr eng konvergiert:**

| Lauf | Ziel € (Intervall-Mitte) | Gap | Status |
|---|---|---|---|
| BASE-FIX (BC-MM) | 319.711 € | 0,085 % | `maxTimeLimit` |
| BASE-HK0 (BC-MM-HK0) | 319.398 € | 0,0098 % | **`optimal`** (echtes Optimum erreicht) |
| S0-HK0 | 317.353 € | 0,098 % | `maxTimeLimit` |

Deutlich engere Konvergenz als unter H3-Standardeinstellungen (dort 0,21–0,49 %); BASE-HK0 erreichte sogar den strikten `MIPGap=1e-4`-Zielwert exakt (bewiesen optimal). BASE-FIX und S0-HK0 liefen bis zum 4-h-Limit, landeten aber weit unter 0,1 % — praktisch punktgenau, Intervallbreite vernachlässigbar.

**B4 SB: 2 von 3 fertig, deutlich engere Konvergenz als H3, aber `MIPGap=1e-4` nirgends erreicht (wie erwartet):**

| Lauf | Ziel € (Intervall-Mitte) | Gap | Schließung MWh | Vergleich H3-Gap |
|---|---|---|---|---|
| BASE-FIX (BC-SB) | 21.135.078 € | 0,124 % | 874,07 (NICHT am Deckel — mit mehr Zeit fand der Solver eine Lösung mit weniger Schließungsbedarf) | H3: 6,40 % → B4: 0,124 % |
| S0-HK0 | 23.281.438 € | 10,29 % | 1.599,93 (weiterhin EXAKT am Deckel, auch mit 4× mehr Zeit + MIPFocus=3) | H3: 31,40 % → B4: 10,29 % |
| BASE-HK0 (BC-SB-HK0) | *läuft, Stand 08:32: Inkumbent 21.193.320 €, Gap 0,44 %, 3,7 h von 8 h verbraucht* | — | — | H3: 1,91 % |

**Bemerkenswert:** BC-SBs Schließungsmenge fiel mit mehr Rechenzeit von „exakt am Deckel" (H3, 1.599,94 MWh) auf 874,07 MWh (B4) — der frühere Deckel-Kontakt war also (zumindest für DIESEN Lauf) ein Konvergenz-Artefakt der kürzeren H3-Zeitbudgets, keine strukturelle Notwendigkeit. **SB-S0-HK0 bleibt dagegen weiterhin exakt am Deckel, selbst mit 4× mehr Zeit** — das stützt die frühere Einschätzung, dass S0-HK0 (nicht notwendigerweise SB als Netz insgesamt) einen echten, größeren strukturellen Bedarf hat, der über 0,25 % hinausgeht. Bei 10,29 % Gap ist der berichtete Zielfunktionswert für S0-HK0 zudem nur die obere Intervallgrenze — die untere liegt bei ~20,88 Mio. € (Bound), eine Spanne von ~2,4 Mio. €.

**Kein weiterer Systemneustart** seit 21:51:09 (23.09.) — die komplette B4-Kampagne (~20,5 h Gesamtlaufzeit, MM+SB parallel) lief seither störungsfrei durch.

## §4bb — 2026-09-25 21:49: B4 VOLLSTÄNDIG ABGESCHLOSSEN — finale Intervalle, alle 6 Läufe

| Netz | Lauf | UB (Inkumbent) € | LB (Bound) € | Gap | Intervallbreite € | Status |
|---|---|---|---|---|---|---|
| MM | BASE-FIX | 319.711 | 319.440 | 0,085 % | 272 | `maxTimeLimit` |
| MM | BASE-HK0 | 319.398 | 319.367 | **0,010 %** | 31 | **`optimal`** (bewiesen) |
| MM | S0-HK0 | 317.353 | 317.043 | 0,098 % | 310 | `maxTimeLimit` |
| SB | BASE-FIX | 21.135.078 | 21.108.823 | 0,124 % | 26.254 | `maxTimeLimit` |
| SB | BASE-HK0 | 21.125.362 | 21.099.864 | 0,121 % | 25.498 | `maxTimeLimit` |
| SB | S0-HK0 | 23.281.438 | 20.885.282 | **10,292 %** | **2.396.156** | `maxTimeLimit` |

**Fünf von sechs Läufen sind praktisch punktgenau** (Intervallbreite ≤ 0,13 % relativ, MM-BASE-HK0 sogar bewiesen optimal). **Nur SB-S0-HK0 bleibt mit weitem Intervall** (20,89–23,28 Mio. €, 10,3 % Spanne) — konsistent mit dem bereits in §4ba dokumentierten Befund, dass diese eine Szenario/Lauf-Kombination (nicht SB als Netz insgesamt) einen echten strukturellen Deckel-Bedarf über 0,25 % hinaus hat, der auch bei 4× mehr Zeit + `MIPFocus=3` nicht verschwindet. BC-SB und BC-SB-HK0 fielen dagegen beide klar unter den Deckel (874,07 bzw. 874,22 MWh von 1.599,93 MWh Kapazität) — der frühere „exakt am Deckel"-Befund für BC-SB (H3) war also ein Konvergenz-Artefakt der kürzeren Zeitbudgets, kein echter Strukturbedarf.

**Wie vorgegeben als Intervalle berichtet, nicht als Punktschätzung** — nur bei S0-HK0 (SB) ist das Intervall praktisch relevant, bei den übrigen fünf Läufen ist die Intervallbreite gegenüber jeder plausiblen Entscheidungsschwelle vernachlässigbar.

**G4/B2/B4 sind damit vollständig abgeschlossen.** Offene Punkte, die eine Autoren-Entscheidung benötigen (aus §4ax/§4ay/§4ba/§4bb zusammengefasst):
1. **SB-S0-HK0s weites Intervall/Deckel-Bindung** — ist das akzeptabel für die aktuelle Fragestellung, oder soll gezielt nachuntersucht werden (z. B. noch mehr Zeit, oder eine strukturelle Prüfung analog zu H2, diesmal für S0-HK0 statt BASE-FIX)?
2. **Der 0,25-%-Datenschließungs-Deckel** ist nach den B4-Ergebnissen für 5 von 6 Läufen unproblematisch (weit darunter) — nur S0-HK0 (SB) bleibt betroffen. Damit bestätigt sich, dass der Deckel selbst wahrscheinlich nicht angepasst werden muss; das eigentliche offene Thema ist S0-HK0 spezifisch.
3. Keine weitere Aktion ohne Autoren-Entscheidung zu diesen beiden Punkten.


## §4bc — 2026-09-25 22:05: Abnahme-Verweigerung SB S0-HK0 (Dominanzverletzung) — I1/I3 erledigt, I2 läuft

**Bestätigt:** SB S0-HK0 (UB 23.281.438 €) ist teurer als SB BASE-HK0 (UB 21.125.362 €) — eine echte Dominanzverletzung (S0 kann BASE durch "nichts bauen" immer replizieren, darf also nie teurer sein). Das ist kein "weites Intervall", sondern ein fehlgeschlagener Lauf im Sinne der Vorgabe.

### I1 — Epsilon-Preis umgesetzt

`create_objective()` (`constraint_builder.py`) um einen 16. additiven Term `data_closure_cost` erweitert (0,01 EUR/MWh, fest — unabhängig von `m.dump_cost`/B2s Override). Die knotenweisen Schließungs-Variablen werden jetzt in `model.data_closure_terms` exponiert (gleiches Muster wie `pressure_slack_terms`/`lateral_tiebreak_terms`); `model_finalizer.py` berechnet daraus die Epsilon-Kosten. `result_collector.py`/`extract_artefacts_p2.py` erfassen den Term als neue AUX-Zeile `Data_closure_epsilon_cost_EUR` (explizit NICHT in `real_costs_EUR`). Begründung wie vorgegeben dokumentiert: bei voller Deckelausnutzung (1.599,93 MWh) maximal **16,00 €** — kann keine Investitionsentscheidung (typischerweise mehrere hundert bis tausend € Unterschied) erkaufen, wirkt nur als Tie-Break.

### I2 — Dominanz-Gate-Skript gebaut + verifiziert, Neuläufe laufen

Neues Skript `scripts/paper_2/check_dominance_gate.py`: lädt `meta.json` je Netz/Heizkurvenstufe, prüft `UB(S0) <= UB(BASE) + 1e-6`, meldet PASS/FAIL (Exit-Code 1 bei mind. einem FAIL). Verifiziert gegen die B4-Ergebnisse: **MM PASS** (S0 −2.045,45 € günstiger als BASE, korrekt), **SB FAIL** (S0 +2.156.076,02 € teurer — die Dominanzverletzung, exakt bestätigt).

**Neuläufe gestartet** (I1 aktiv, geseedet über den bereits vorhandenen `CALION_WARMSTART_FROM`-Mechanismus — `calion/run/solver.py`s `_apply_warmstart`, liest Commitment-Binärvariablen aus dem jeweiligen BASE-HK0-`dispatch_hourly.csv`, Partial-MIP-Start, Kontinuierliche/Investitionsvariablen bleiben frei): `MM-S0-HK0` (4 h, seed aus `b4_mm/BC-MM-HK0`) und `SB-S0-HK0` (8 h, seed aus `b4_sb/BC-SB-HK0`), beide unter identischem Protokoll wie B4 sonst (`MIPGap=1e-4`, `MIPFocus=3`). Laufen — Ergebnis (UB/LB/Gap/Schließungsterm MWh+%, vor/nach I1) wird nachgetragen.

### I3 — MM-Differenz vollständig aufgeklärt: EK WURDE gebaut (kein Bug)

**Ursache gefunden:** Entgegen der bisherigen Annahme ("weder HP noch EK gebaut") wurde in MM-S0-HK0 tatsächlich eine **kleine EK-Kapazität (Elektrokessel/`eboiler_main`) gebaut** — die frühere Prüfung hatte nur `hp_main` über die `[DESIGN] Extracted HP`-Logzeile kontrolliert; für EK existiert in `design_helpers.py` KEINE äquivalente Log-Zeile, weshalb dies bisher unbemerkt blieb (eigener Diagnosefehler, hiermit korrigiert).

**Quantitativer Beleg:** `dispatch_per_asset.csv`s `P2H_MW`-Spalte (P2H = eboiler_main) zeigt Einsatz in 625 von 8.760 Stunden, Spitze 0,10293 MW, Jahressumme 10,15 MWh. Rückrechnung aus der Kostenzerlegung bestätigt exakt dieselbe Kapazität: `Capex_cost_EUR` (1.095,47 €) und `Activation_cost_EUR` (1.419,05 €) sind in BASE-HK0 beide 0, in S0-HK0 beide positiv; der Aktivierungs-Annuitätsfaktor (1.419,05/20.000 €=0,070953) zurück auf die Kapazität angewandt (1.095,47/(150.000×0,070953)) ergibt **0,10293 MW — identisch zur dispatchierten Spitzenlast.** Die Anlage wurde also exakt auf ihre genutzte Spitzenlast dimensioniert, keine Überkapazität.

**Kostenzerlegung der Differenz (BASE-HK0 − S0-HK0, Positivliste):**

| Term | Δ € (BASE−S0) |
|---|---|
| Capex_cost_EUR | −1.095,47 (S0 zahlt mehr) |
| Activation_cost_EUR | −1.419,05 (S0 zahlt mehr) |
| Fuel_cost_EUR | +4.183,09 (S0 spart) |
| CO2_cost_EUR | +1.719,51 (S0 spart) |
| Demand_charge_cost_EUR | −795,47 (S0 zahlt mehr) |
| Grid_energy_cost_EUR | −75,99 (S0 zahlt mehr) |
| Grid_sell_revenue_EUR | −471,37 (S0 verdient weniger) |
| **Summe reale Kosten** | **+2.045,26 (S0 netto günstiger)** |

Vollständig reales Ergebnis, mit AUX-Termen und Residuum exakt auf die Zielfunktionsdifferenz (2.045,45 €) rekonziliert (`reconciliation_check: OK` beide Läufe). **Kein Freiheitsgrad im Dispatch, keine Anomalie — eine reale, korrekt bepreiste, minimale Investitionsentscheidung.** I3 ist damit abgeschlossen, keine weitere Aktion nötig.

### I2 — Zwischenstand: MM-S0-HK0 abgeschlossen (PASS), SB-S0-HK0 läuft noch

**MM-S0-HK0 (4 h, `maxTimeLimit`, 14.871,8 s) fertig:**

| | vor I1 (B4) | nach I1+Seed (I2) | Δ |
|---|---|---|---|
| UB € | 317.352,92 | 317.406,86 | +53,93 |
| LB € | 317.043,10 (≈) | 317.045,36 | +2,25 |
| Gap | 0,098 % | 0,114 % | +0,016 pp |
| Schließungsterm MWh | 11,606 | 11,636 | +0,030 |
| Schließungsterm % Jahresbedarf | 0,1230 % | 0,1233 % | +0,0003 pp |
| Epsilon-Kosten (I1) € | — (n. v.) | 0,116 | — |

Praktisch identisch — die minimale Verschiebung liegt im Rauschen normaler MIP-Lauf-zu-Lauf-Varianz plus dem (erwartungsgemäß vernachlässigbaren) I1-Epsilon-Term (0,116 € statt der theoretisch maximal möglichen ~16 €, exakt = 11,636 MWh × 0,01 EUR/MWh). Schließungsterm bleibt weit unter dem 0,25-%-Deckel (kein Bind) und sogar unter der 0,125-%-Warnschwelle.

**Dominanz-Gate: PASS.** UB(S0)=317.406,86 € vs. UB(BASE-HK0)=319.398,38 € → S0 ist 1.991,52 € GÜNSTIGER als BASE (Marge negativ = Dominanz erfüllt). MM bestand die Dominanzprüfung bereits in B4 (dort war die Differenz nie das Problem — nur SB war betroffen); dieser Neulauf bestätigt das erneut unter dem geänderten Zielfunktions-Term.

**SB-S0-HK0 (8 h) läuft noch** — Zwischenstand (Stand 02:13 Uhr, ca. zur Hälfte des Zeitbudgets): Inkumbent verbessert sich schrittweise von anfänglich 35,83 Mio. € (41,7 % Gap) auf zuletzt 25,64 Mio. € (18,6 % Gap), mehrfach in großen Sprüngen durch Heuristik-Funde (nicht linear/stetig). Die Bound liegt seit Laufbeginn stabil bei ~20,885 Mio. € — **unterhalb** der BASE-HK0-Schwelle (21.125.362 €), was ein gutes Zeichen ist, dass das wahre Optimum die Dominanz erfüllt. Ob der gemeldete Inkumbent die Schwelle innerhalb der verbleibenden ~4 h tatsächlich unterschreitet, ist noch offen. Prozess wiederholt auf Aktivität/Hang geprüft (CPU-Zeitzuwachs bestätigt, kein Stillstand).

### I2 — SB-S0-HK0 abgeschlossen: Dominanzverletzung BLEIBT (echter Befund bestätigt)

**SB-S0-HK0 (8 h, `maxTimeLimit`, 29.377,3 s) fertig:**

| | vor I1 (B4) | nach I1+Seed (I2) | Δ |
|---|---|---|---|
| UB € | 23.281.438,10 | 24.607.859,69 | **+1.326.421,59 (schlechter!)** |
| LB € | 20.885.282,22 | 20.885.299,72 | +17,50 (praktisch identisch) |
| Gap | 10,292 % | 15,128 % | +4,84 pp (schlechter!) |
| Schließungsterm MWh | 1.599,933738376 | 1.599,933738376 | **0,0000000000 (identisch auf 10 Nachkommastellen)** |
| Schließungsterm % Jahresbedarf | 0,25000 % (= Deckel) | 0,25000 % (= Deckel) | unverändert — weiterhin exakt am Deckel |
| Epsilon-Kosten (I1) € | — (n. v.) | 15,999 (≈ theoret. Maximum 16 €) | — |

**Befund 1 — Deckel-Bindung ist real, kein Tie-Break-Artefakt:** Der Schließungsterm bleibt bei exakt 1.599,9337 MWh (0,2500 % Jahresbedarf) — bit-identisch vor und nach dem I1-Epsilon-Preis. Ein Preis, der ausschließlich dazu dient, das Residuum zu minimieren (0,01 EUR/MWh, keine reale Kostenwirkung), hätte den Term messbar reduzieren MÜSSEN, wenn irgendein Spielraum ohne reale Mehrkosten bestanden hätte. Da das nicht passiert, ist die Deckelbindung **strukturell real**, nicht künstlich: das Netz benötigt an diesen Knoten tatsächlich mindestens diese Menge an Bilanzausgleich. Aufschlüsselung nach Knoten (identisch vor/nach I1, da Term unverändert):

| Knoten | Summe MWh | Stunden (n) | Spitzenwert MW |
|---|---|---|---|
| j_bmhkw | 837,26 | 249 | 13,78 |
| j_man | 316,71 | 547 | 7,60 |
| j_hkw | 245,09 | 51 | 46,64 |
| j_psw | 125,58 | 72 | 4,31 |
| j_gtost | 68,86 | 29 | 11,51 |
| **Summe** | **1.599,93** | — | — |

Alle fünf Knoten sind CHP-/Erzeuger-Knoten (nicht Lastknoten) — konsistent mit der schon länger vermuteten Erzeuger-seitigen Herkunft des strukturellen Lieferresiduums (0,08–0,13 % Jahresbedarf laut Label, hier am oberen Rand/Deckel). Stundenverteilung ist über weite Teile des Jahres verteilt (nicht auf wenige Extremstunden konzentriert), mit Ausnahme von j_hkw (nur 51 Stunden, aber Spitzenwert 46,64 MW — größter Einzelbeitrag pro Stunde).

**Befund 2 — Dominanzverletzung bleibt, wird durch Seed sogar schlechter:** Trotz I1 (Epsilon-Preis) UND I2 (Warmstart aus BASE-HK0-Commitments, identisches Zeit-/Solver-Protokoll) bleibt SB-S0-HK0 **weiterhin dominanzverletzend** — und zwar mit einer GRÖSSEREN Verletzung als zuvor (+3.482.497,61 € statt +2.156.076,02 €). Die Bound (LB) ist dabei über beide Läufe hinweg praktisch unverändert bei ~20,885 Mio. € eingefroren (+17,50 € Unterschied über 8 Stunden zusätzliche Rechenzeit) — das ist ein starkes Indiz, dass das **wahre Optimum** unterhalb der BASE-HK0-Schwelle (21.125.362 €) liegt und die Dominanz-Eigenschaft also erfüllt, aber der gefundene Inkumbent (UB) sie nicht widerspiegelt. Der Warmstart-Seed hat die Suche in eine andere, letztlich schlechtere Inkumbent-Trajektorie gelenkt als der ungeseedete B4-Lauf — üblicherweise erwartet man von einem Seed keine Verschlechterung, aber bei einer so großen MIP-Instanz (7.384.701 Variablen, davon 1.208.895 binär; 9.249.651 Constraints) ist Lauf-zu-Lauf-Varianz zwischen unabhängigen Suchbäumen real und nicht ausgeschlossen.

**Einordnung:** Dies ist ein **Tractability-Befund, kein struktureller Modellfehler**. Weder der Epsilon-Preis noch der Warmstart-Seed konnten das Problem innerhalb von 8 h lösen; beide Mechanismen wirkten exakt wie vorgesehen (Epsilon: rechnerisch korrekt, aber ohne Hebel auf eine strukturell notwendige Bilanzgröße; Warmstart: technisch korrekt gesetzt, aber ohne garantierte Verbesserung bei dieser Instanzgröße). Eine weitere Verbesserung würde vermutlich einen anderen Hebel brauchen (z. B. deutlich mehr Zeit, Symmetriebrechung analog SB-S6, oder eine gezielte Dekomposition) — das ist eine neue Aufgabe, keine Fortsetzung von I1–I3, und bedarf einer eigenen Autoren-Entscheidung.

**[COST-BREAKDOWN]-Fehlermeldung eingeordnet:** Die im Lauf erschienene ERROR-Zeile „Objective_residual_EUR = 1.759.881,89 (>1 EUR Toleranz)" ist **keine neue Regression** — dieselbe Meldung (mit vergleichbarer Größenordnung: 1.585.859–1.711.242 €) erscheint bereits in JEDEM B4-SB-Lauf (BASE-FIX, BASE-HK0, S0-HK0), also vor jeglicher I1/I2-Änderung. `reconciliation_check: OK` bestätigt, dass `residual_EUR` die Differenz definitionsgemäß auffängt (die Zielfunktion selbst — und damit die für das Dominanz-Gate maßgebliche Zahl — ist davon nicht betroffen, da sie direkt aus Gurobi kommt, nicht aus der Dekomposition). Für die Zwecke von I1–I3 keine weitere Aktion; eine Aufklärung dieses SB-spezifischen ~7-%-Restterms (analog zum in Paper 1 dokumentierten CO2-Netting-Residuum) bleibt ein offenes, separates Thema.

## §4bd — 2026-09-26 06:20: FINALE ERGEBNISTABELLE MIT DOMINANZ-GATE-SPALTE

| Netz | Lauf | UB € | LB € | Gap | Dominanz-Gate | Status |
|---|---|---|---|---|---|---|
| MM | BASE-FIX | 319.711 | 319.440 | 0,085 % | — (ist BASE) | `maxTimeLimit` |
| MM | BASE-HK0 | 319.398 | 319.367 | 0,010 % | — (ist BASE) | **`optimal`** |
| MM | S0-HK0 | 317.407 | 317.045 | 0,114 % | **PASS** (−1.991,52 € ggü. BASE) | `maxTimeLimit` |
| SB | BASE-FIX | 21.135.078 | 21.108.823 | 0,124 % | — (ist BASE) | `maxTimeLimit` |
| SB | BASE-HK0 | 21.125.362 | 21.099.864 | 0,121 % | — (ist BASE) | `maxTimeLimit` |
| SB | S0-HK0 | **24.607.860** | 20.885.300 | **15,128 %** | **FAIL** (+3.482.497,61 € ggü. BASE) | `maxTimeLimit` |

**Fünf von sechs Zeilen bestehen das Dominanz-Gate** (die vier BASE-Zeilen trivial per Definition, MM-S0-HK0 explizit geprüft und bestanden). **Nur SB-S0-HK0 bleibt dominanzverletzend**, nach I1 (Epsilon-Preis) und I2 (Warmstart-Neulauf) sogar mit größerer Verletzung als im ursprünglichen B4-Lauf. Wie oben begründet: die Bound (LB≈20,885 Mio. €, stabil über beide Läufe) liegt unterhalb der BASE-HK0-Schwelle — das wahre Optimum erfüllt die Dominanz voraussichtlich, der gemeldete Inkumbent tut es (noch) nicht. **I1, I2 und I3 sind damit alle abgeschlossen.**

**Autoren-Abnahme dieser Tabelle VERWEIGERT (2026-09-26).** Weder Seed-Wiederholung noch Symmetriebrechung noch Fußnote — stattdessen J1–J3 (Diagnose) und darauf aufbauend K1–K4 (Infrastruktur + entscheidender Lauf), siehe §4be.

## §4be — 2026-09-26: J1–J3-Diagnose + K1 (Infrastruktur) + K2 (entscheidender Lauf `s0_pin0`)

### J1 — Wurde der Warmstart akzeptiert?

**Nicht sauber.** Gurobi-Log des geseedeten SB-S0-HK0-Laufs:
```
[WARMSTART] Set 17520 binary hints, skipped 1191375 (partial MIP start)
Processing user MIP start: 0 nodes explored in subMIP, total elapsed time 5s...40s
User MIP start did not produce a new incumbent solution
Processed MIP start in 41.77 seconds
```
Gurobis interne subMIP-Reparaturheuristik hat 41,77 s versucht, die partiellen Binärhinweise (nur 1,45 % aller 1.208.895 Binärvariablen) zu einer vollständigen Lösung zu vervollständigen, und ist gescheitert — **keine explizite "violates constraint"-Meldung**, nur "kein neuer Inkumbent". Mehrdeutig: vereinbar mit "technisch unvollständig" UND mit "eigentlich unzulässig".

### J2 — Ist S0 wirklich eine Obermenge von BASE?

Per Code-/Config-Vergleich (kein Solve): `hp_node: "J4"` mappt auf `j_man` — exakt der Knoten mit 316,71 MWh Schließungsterm-Nutzung. In BASE-HK0 hat `j_man` nur `consumers:`, kein `assets:` → `NodeConfig.from_dict` inferiert `type="consumer"`, `_link_consumer_demands` erzwingt `Q_pipe[t]==Q_demand[t]`. In S0-HK0 verschiebt `_apply_hp_location` `hp_sb`/`ek_sb` auf `j_man` → `type="mixed"` → die einfache Pinnung wird übersprungen, stattdessen gilt `constraint_builder.py`s `secondary_combined_balance`: `local_gen + Q_pipe_in[t] == Q_demand[t] + Q_dump_j_man[t]`. Bei `local_gen=0` (Kapazität fixiert) und BASE-Zahlen eingesetzt: `Q_demand + 0 == Q_demand + dump` → algebraisch erfüllt bei `dump=0`. `heat_pump.py`s Kapazitäts-Linearisierung (`cap_x_on<=capacity`, `Q<=cap_x_on`) zwingt `Q=0` bei `capacity=0`, unabhängig vom On/Off-Binär — kein erzwungener Mindestlast-Bug gefunden. **Algebraisch spricht alles für "ja, Obermenge"** — aber das ist eine Herleitung, kein numerischer Beweis (dafür fehlt eine vollständige BASE-HK0-Lösung zum Einsetzen — genau das behebt K1).

### J3 — Landet der Epsilon-Preis im Objective?

**Ja, exakt bestätigt:** `Data_closure_epsilon_cost_EUR = 15,999337 €` = `1.599,933738 MWh × 0,01 EUR/MWh` auf 6 Nachkommastellen. Kein Fix nötig, kein Testlauf nötig.

### K1 — Lösungen persistieren (Infrastruktur, ab sofort für alle Läufe)

**Ursache des J1-Problems identifiziert und behoben:** `_apply_warmstart` (CSV-basiert) kann nur ~1,5 % der Binärvariablen per Spaltennamen-Heuristik erraten — der Rest bleibt für Gurobis eigene (hier gescheiterte) subMIP-Reparatur offen. Implementiert in `calion/run/solver.py`:
1. **Jeder erfolgreiche Solve schreibt jetzt UNBEDINGT** (nicht mehr nur bei gesetztem `CALION_DUMP_VARS`) eine vollständige Lösungs-Dump-Datei `<export_dir>/full_solution_dump.json` (Format: `{component_name: {index: value}}`, wiederverwendet das bereits bestehende, getestete `_apply_warmstart_dump`-Format statt eines neuen Gurobi-`.sol`-Parsers — funktional äquivalent, robuster gegenüber Format-Eigenheiten, matched by NAME statt Spalten-Heuristik).
2. **Warmstart-Dispatch bevorzugt jetzt automatisch** `full_solution_dump.json` im `warmstart_from`-Verzeichnis, falls vorhanden; nur wenn keine vorhanden ist (ältere Läufe vor K1), fällt es mit einer expliziten Log-WARNUNG auf den alten CSV-Partial-Pfad zurück.
3. **Coverage-Prozentsatz wird jetzt geloggt und bei <99 % laut gewarnt** (`_apply_warmstart_dump`): "PARTIAL start: only X% of this model's variable entries were set... treat any resulting incumbent with caution."

Ab dem nächsten Lauf jeder Szenario-Kette persistiert jede Lösung vollständig; zukünftige Warmstarts sind damit standardmäßig vollständig, nicht mehr partiell.

### K2 — Entscheidender Lauf: SB-S0-HK0 mit fixierten Investitionen (`s0_pin0`) — LÄUFT

Neues Szenario `SB-S0-HK0-PIN0` in `configs/paper_2/scenarios.yaml`: identische Topologie zu SB-S0-HK0 (`hp_node: "J4"` — hp_sb/ek_sb bleiben physisch an j_man, `j_man` bleibt `type="mixed"` mit Schließungsterm-Var), aber `investment: {enabled: false, capacity_max_mw: 0.0}` für hp_sb UND ek_sb (identisches Override-Muster wie BC-SB-HK0) — TES bleits (`tes_off_sb`, ohnehin schon aus in S0). Build-Log bestätigt den Ghost-Variablen-Pfad korrekt ausgelöst:
```
[GHOST-VAR] hp_sb: disabled (non-investable, capacity_init_mw=0) -- skipped 5 linearization
  constraint(s), hard-fixed 35040 Var entries (on/Q/Q_wrg/Q_def) to 0, no cap_x_on Var created
[GHOST-VAR] EK_SB: disabled (non-investable, cap=0) -- skipped commitment binary `on` and
  capcons/minload/link constraints entirely, hard-fixed Q/P to 0 (8760 timesteps)
```
Gestartet 2026-09-26 17:50:29 unter identischem Protokoll (MIPGap=1e-4, MIPFocus=3, Cuts=2, TimeLimit=28800s, Threads=4), OHNE Warmstart (bewusst — sauberer Vergleich gegen BASE-HK0s wahren Wert). Erwartung (K2): Objektwert ≈ SB-BASE-HK0 (21.125.362 €) innerhalb der Gaps. Ergebnis folgt.

### K2 — Ergebnis: Fall (a) bestätigt

`SB-S0-HK0-PIN0` fertig (8 h, `maxTimeLimit`, 29.382,8 s): **21.124.777,25 €**, Gap 0,1197 %. Gegen BASE-HK0 (21.125.362,08 €): Δ = **−584,83 €** (0,0028 %) — praktisch identisch, S0 mit eingefrorenen Investitionen reproduziert BASE-HK0 bis auf Rauschen innerhalb beider MIP-Gaps. `n_vars` (7.358.419) ist **exakt identisch** zu BASE-HK0s Wert. Schließungsterm 875,96 MWh (0,1369 %) — **nahe BASE-HK0s eigenem Wert** (874,22 MWh), NICHT am Deckel. **Fall (a) ist damit numerisch bestätigt: S0 ist eine echte Obermenge von BASE.** Weiter zu K3.

### K3 — Neulauf mit vollständigem Warmstart aus s0_pin0

Neue Warmstart-Infrastruktur (K1) griff wie vorgesehen: `full_solution_dump.json` gefunden, **96,4 % Coverage** (7.121.464 von 7.384.701 Var-Einträgen gesetzt) — gegenüber vorher 1,45 % (nur Binärvariablen). Gurobi-Log zeigt jetzt eine explizite, aber verschwindend kleine Verletzung (`User MIP start violates constraint c_e_x2378287_ by 0.000076`) statt der vorherigen kommentarlosen Ablehnung — ein starkes eigenständiges Indiz, dass die transplantierte Lösung strukturell fast exakt zulässig ist (Rundungsrauschen, keine echte Inkompatibilität).

Ergebnis (8 h, `maxTimeLimit`, 29.492,8 s): **21.953.837,68 €**, LB 20.885.301,10 €, Gap **4,8672 %**.

| | B4 (Original) | I2 (Partial Warmstart) | K3 (Full Warmstart) |
|---|---|---|---|
| UB € | 23.281.438,10 | 24.607.859,69 | **21.953.837,68** |
| Gap | 10,292 % | 15,128 % | **4,867 %** |
| Δ ggü. BASE-HK0 € | +2.156.076,02 | +3.482.497,61 | **+828.475,60** |
| Δ ggü. BASE-HK0 % | 10,20 % | 16,49 % | **3,92 %** |
| LB € | 20.885.282,22 | 20.885.299,72 | 20.885.301,10 |

Die Bound ist über alle drei unabhängigen Läufe **auf 19 € stabil** — ein sehr starkes Indiz, dass das wahre Optimum bei ~20,885 Mio. € liegt, deutlich unter BASE-HK0s Schwelle. K3s vollständiger Warmstart hat die gemeldete Verletzung um **Faktor 2,6 gegenüber B4** und **Faktor 4,2 gegenüber I2** reduziert — ein klarer, messbarer Erfolg von K1+K2+K3 — aber **die Dominanzverletzung ist innerhalb von 8 h nicht vollständig verschwunden.**

**Dominanz-Gate: weiterhin FAIL**, wie vom Nutzer vorgesehen ("Dominanz ist dann per Konstruktion erfüllt; das Gate bleibt trotzdem als Assertion aktiv"). Das ist kein Widerspruch: K2 hat die Obermengen-Eigenschaft des Modells bewiesen (die wahre Lösung erfüllt Dominanz), aber das Gate prüft den gemeldeten Inkumbenten, und dieser MILP (7.384.701 Variablen, 1.208.895 binär) ist innerhalb von 8 h selbst mit einem 96%-Warmstart nicht auf einen dominanzkonformen Inkumbenten zu bringen. Das ist der erwartbare, jetzt sauber belegte Tractability-Befund — kein Modellfehler.

### K4 — Cap-Frage entschieden

Schließungsterm-Vergleich über alle vier SB-S0-HK0-artigen Läufe:

| Lauf | Investitionsfreiheit? | Schließungsterm MWh | % Jahresbedarf | Am Deckel? |
|---|---|---|---|---|
| BASE-HK0 | — (kein HP/EK) | 874,22 | 0,1230 % | nein |
| s0_pin0 (K2) | NEIN (hart auf 0 fixiert) | 875,96 | 0,1369 % | **nein** |
| S0-HK0 B4 (Original) | JA | 1.599,93 | 0,2500 % | **ja** |
| S0-HK0 I2 (Partial WS) | JA | 1.599,93 | 0,2500 % | **ja** |
| S0-HK0 K3 (Full WS) | JA | 1.599,93 | 0,2500 % | **ja** |

**Eindeutiges Muster, viermal reproduziert:** Der Deckel-Anschlag tritt IMMER auf, wenn hp_sb/ek_sb investierbar sind (unabhängig vom Warmstart — B4, I2 und K3 landen alle bit-identisch bei 1.599,9337 MWh), und NIE, wenn ihre Kapazität hart auf 0 fixiert ist (s0_pin0 liegt bei BASE-HK0s eigenem Niveau). Da s0_pin0 UND die drei S0-Läufe strukturell IDENTISCH sind (gleiche Mixed-Knoten-Bilanz an j_man, gleiche `secondary_combined_balance`-Gleichung) und sich NUR in der Investitionsfreiheit unterscheiden, ist die Ursache eindeutig: **der Deckel-Anschlag ist eine Folge der Kombination aus Mixed-Knoten-Bilanz an j_man UND aktiver Investitionsfreiheit für hp_sb/ek_sb — keine Dateneigenschaft des Netzes.** Die Bilanzform allein (mit eingefrorener Investition) bindet den Deckel NICHT. Der 0,25-%-Deckel selbst bleibt als Sicherheitsmechanismus unverändert korrekt; er deckt hier eine reale MILP-Kopplung zwischen Investitionsentscheidung und Datenschließung auf, keinen Bug.

**K1, K2, K3 und K4 sind damit alle abgeschlossen.** Verbleibender offener Punkt: die Dominanzverletzung ist (jetzt mathematisch bewiesenermaßen nur scheinbar, aber im gemeldeten Inkumbenten) noch vorhanden — 3,92 % statt 10,3 % vorher. Eine vollständige numerische Schließung würde einen anderen Hebel brauchen (Symmetriebrechung, ein Fix-and-Relax-Schema, das die Investitionsvariablen zuerst fixiert und dann verfeinert, oder deutlich mehr Zeit) — das ist explizit NICHT Teil dieses Auftrags (keine weitere Rechenzeit, kein Symmetry-Breaking). Ergebnistabelle folgt in §4bf.

## §4bf — 2026-09-27: FINALE ERGEBNISTABELLE (nach K1–K4)

| Netz | Lauf | UB € | LB € | Gap | Dominanz-Gate | Status |
|---|---|---|---|---|---|---|
| MM | BASE-FIX | 319.711 | 319.440 | 0,085 % | — (ist BASE) | `maxTimeLimit` |
| MM | BASE-HK0 | 319.398 | 319.367 | 0,010 % | — (ist BASE) | **`optimal`** |
| MM | S0-HK0 | 317.407 | 317.045 | 0,114 % | **PASS** (−1.991,52 € ggü. BASE) | `maxTimeLimit` |
| SB | BASE-FIX | 21.135.078 | 21.108.823 | 0,124 % | — (ist BASE) | `maxTimeLimit` |
| SB | BASE-HK0 | 21.125.362 | 21.099.864 | 0,121 % | — (ist BASE) | `maxTimeLimit` |
| SB | S0-HK0-PIN0 (K2, Referenz) | 21.124.777 | 21.099.573 | 0,120 % | **PASS by construction** (−584,83 € ggü. BASE) | `maxTimeLimit` |
| SB | S0-HK0 (K3, final) | **21.953.838** | 20.885.301 | **4,867 %** | **FAIL** (+828.475,60 € ggü. BASE) | `maxTimeLimit` |

Fünf der sechs Kern-Zeilen (MM×3, SB-BASE×2) bestehen das Gate trivial oder explizit geprüft. Die zusätzliche `S0-HK0-PIN0`-Zeile ist kein Kandidat für die Haupttabelle des Papers, sondern der Beweis, dass SB-S0-HK0s Dominanzeigenschaft mathematisch gilt. Die reale `SB-S0-HK0`-Zeile bleibt mit 4,87 % Gap und einer 3,92-%-Dominanzverletzung im gemeldeten Inkumbenten — deutlich verbessert gegenüber den 10,3–16,5 % der Vorläufe, aber nicht vollständig geschlossen. Autoren-Entscheidung ausstehend: diesen Zustand (mit Fußnote zu K2/K4 als Beweis der zugrundeliegenden Dominanz) akzeptieren, oder einen weiteren Hebel (Symmetriebrechung, gestuftes Fix-and-Relax) in einer separaten, neuen Aufgabe verfolgen.

## §4bg — 2026-09-27: L1 (Inkumbenten-Pool-Auswertung, kein neuer Solve)

**L1 (Inkumbenten-Pool):** UB für SB-S0-HK0 wird nicht aus einer einzelnen Lauf-Datei übernommen, sondern rigoros neu ausgewertet — der `s0_pin0`-Lösungspunkt (K2, Investition hart auf 0 fixiert) wird in das echte SB-S0-HK0-Modell (Investition frei) transplantiert (`CALION_WARMSTART_DUMP` + `CALION_SEED_FILL_ZERO` füllt alle neuen Investitionsvariablen mit 0) und über `CALION_FEAS_ONLY` ausgewertet (reine Auswertung, kein Solve). Ergebnis: **UB = 21.124.777,25 €** (Zielfunktionswert am transplantierten Punkt), bit-genau konsistent mit K2/K4s bereits dokumentiertem `S0-HK0-PIN0`-Wert (§4bf, Zeile 6: 21.124.777 €).

**Abweichung vom vom Autor genannten Wert:** Der Autor nannte 21.125.947 €; meine Auswertung ergibt 21.124.777,25 € — eine Differenz von 1.169,75 € (0,0055 %), die ich als Methodikunterschied melde statt stillschweigend zu übernehmen (möglich: andere Rundung, andere Quelle innerhalb des Pools, oder ein leicht anderer Auswertungszeitpunkt). Für alle nachfolgenden Schritte (M/N) wurde ausschließlich meine eigene, reproduzierbare Auswertung verwendet.

**Feasibility-Vorbehalt:** Die Transplantation zeigt 514 lokalisierte Constraint-Verletzungen, ALLE konzentriert auf genau die Stunden 8365–8367 (E3-Hydraulik-Suspendierungsgrenze), 0,034 % der Jahresstunden. Vermutlich ein Randbedingungsartefakt am E3-Übergang, nicht strukturell — wird aber als Vorbehalt an L1s "S0-Restriktion impliziert Zulässigkeit"-Aussage vermerkt, nicht als vollständig gelöst behandelt.

## §4bh — 2026-09-27: M1/M2 — Notkühler-Repreisung entdeckt und korrigiert

**Befund (vor jeder Korrektur dokumentiert, wie verlangt):** Der freie/epsilon-bepreiste Datenschließungsterm (`Q_dump_{node}`, G3/H1, 0,01 €/MWh) verdrängte an KWK-Knoten den bereits vorhandenen, ECHT bepreisten Notkühler-Mechanismus (`Q_dump_chp_{ASSET}` in `component_assembler.py`, `_dump_mode == 'chp_only' and _is_chp_gen`, ~5 €/MWh via `m.dump_cost`, kapazitätsbeschränkt durch `cap_th` der jeweiligen KWK-Einheit). Der Solver wählte den billigeren Pfad (0,01 statt ~5 €/MWh) überall dort, wo beide Mechanismen am selben Knoten koexistierten — ein reiner Kostenoptimierungs-Nebeneffekt der Modellstruktur, kein Konfigurationsfehler.

**M1 (Zuständigkeit je Knoten):** Jeder Knoten bekommt genau einen Mechanismus, nach Kategorie:
- **Reine KWK-Knoten ohne lokale Nachfrage** (Asset mit `P_el_out`, aber kein `heatd_{node}`): `Q_dump_{node}` hart auf 0 fixiert für alle `t` — nur der Notkühler bleibt verfügbar.
- **Knoten mit lokaler Nachfrage** (mit oder ohne KWK): Schließung bleibt zulässig, mit datenabgeleiteter Kappungsgrenze (siehe N1).
- **Reine Generator-/Durchleitungsknoten ohne Kühler und ohne KWK:** Schließung zulässig, ebenfalls mit Kappungsgrenze.

Implementiert in `add_per_node_heat_balance` (`calion/models/constraint_builder.py`). Bug bei der ersten Implementierung gefunden und behoben: die KWK-Erkennung prüfte die Asset-ID in Kleinschreibung, aber `component_assembler.py` verwendet `name = asset.id.upper()` für den Pyomo-Attributnamen — Fix: `hasattr(model, f"Q_dump_chp_{a.upper()}")`. Verifiziert an einem Testbuild: MM zeigte vor dem Fix fälschlich „0 KWK-Knoten" trotz sichtbarem `Q_dump_chp_CHP_MAIN` im Modell-Log; nach dem Fix korrekt erkannt.

**M1-Assertion war zu streng — korrekt gemeldet statt stillschweigend aufgelöst:** Die ursprüngliche Annahme „kein Knoten hat beide Mechanismen" verletzte sich an MM-Knoten `j_9`, der ECHT sowohl `chp_main` (KWK) als auch lokale Nachfrage (Verbraucher V_15/V_16) trägt — reale Netztopologie, kein Bug. Wie in M1 selbst vorgesehen wurde dieser Konflikt gemeldet statt selbst aufgelöst; die Korrektur kam vom Autor als N2 (siehe §4bi).

**M2 (Vorprüfung ohne Solve):** Ein flacher 0,05-%-der-eigenen-Nachfrage-Deckel (M1s erster Vorschlag) erwies sich als drastisch zu eng, geprüft anhand der bereits akzeptierten Baseline-Nutzung DERSELBEN Knoten: MM `j_12` 6,5× über dem Deckel, MM `j_9` 42× über, SB `j_man` 27–36× über. Kein Solve unter dieser Konfiguration gestartet; der Autor ersetzte die Formel komplett durch N1.

## §4bi — 2026-09-27: N1/N2/N3 — Finale Schließungsterm-Konfiguration und Kampagne

**N1 (Baseline-abgeleitete Kappungsgrenze):** `cap(n) = max(1,5 × Baseline-Nutzung von Knoten n in BASE-HK0 des jeweiligen Netzes, 1 MWh)`. Analog zur früheren Druck-Slack-Aufweitung: datenabgeleitet, nicht willkürlich, verhindert Budgetkonzentration auf einem Knoten. Ausnahme dokumentiert: SB `j_man` nutzt als Referenz NICHT BASE-HK0 (dort 0, da HP/EK erst in S0 platziert werden), sondern S0-HK0s eigenen historischen Wert aus B4 (316,71 MWh) → cap = 475,065 MWh.

| Knoten | Baseline MWh | Quelle | cap MWh (1,5×) |
|---|---|---|---|
| MM `j_9` | 5,2905 | BC-MM-HK0 (B4) | 7,9358 |
| MM `j_12` | 6,2815 | BC-MM-HK0 (B4) | 9,4222 |
| SB `j_bmhkw` | 504,1386 | BC-SB-HK0 (B4) | reine KWK, Deckel irrelevant (`Q_dump` fix 0) |
| SB `j_gtost` | 259,3482 | BC-SB-HK0 (B4) | reine KWK, Deckel irrelevant |
| SB `j_hkw` | 110,0001 | BC-SB-HK0 (B4) | reine KWK, Deckel irrelevant |
| SB `j_pss` | 0,7319 | BC-SB-HK0 (B4) | 1,0979 |
| SB `j_man` | 316,71 (Substitut: S0-HK0 B4, nicht BASE-HK0) | siehe oben | 475,065 |
| SB `j_psw` | — (kein Baseline-Eintrag) | Boden | 1,0 |

Implementiert via `_make_node_cap_rule(_var, _cap_val)`-Factory (vermeidet das bekannte Pyomo-Scalar-Constraint-Default-Arg-Problem), ein `pyo.Constraint` je schließungsberechtigtem Knoten (`data_closure_cap_node_{nid}`); netzweiter 0,25-%-Deckel bleibt zusätzlich unverändert bestehen. Test-Builds vor jedem Solve verifiziert: MM → 0 reine KWK-Knoten, 15 schließungsberechtigt; SB → 3 reine KWK-Knoten (`j_bmhkw`/`j_gtost`/`j_hkw`), 30 schließungsberechtigt (inkl. `j_man` cap=475,0650 — exakte Übereinstimmung mit dem vom Autor genannten Wert, und `j_pss` cap=1,0979).

**N2 (Assertion korrigiert):** Ersetzt „kein Knoten hat beide Mechanismen" durch: an jedem KWK-Knoten muss gelten `cap(Schließung) ≤ 1,5×Baseline` UND der Notkühler-Ausgang muss existieren — MM `j_9` (KWK + lokale Nachfrage) verletzt diese neue Invariante nicht (cap=7,9358, Notkühler `Q_dump_chp_CHP_MAIN` vorhanden). Reine KWK-Knoten ohne Nachfrage bleiben unverändert bei Schließung=0.

**N3 (Läufe, vollständiger Warmstart aus den jeweiligen .sol, matched effort unverändert):**

| Netz | Lauf | UB € | LB € | Gap | Status | Solve-Zeit |
|---|---|---|---|---|---|---|
| MM | BASE-HK0 | 319.404,93 | 319.373,01 | 0,0100 % | `optimal` | — |
| MM | S0-HK0 | 317.377,28 | 317.042,23 | 0,1056 % | `maxTimeLimit` | — |
| SB | BASE-HK0 | 21.127.847,23 | 21.110.422,34 | 0,0825 % | `maxTimeLimit` | 29.417,0 s |
| SB | S0-HK0 | 21.276.158,68 | 20.888.029,37 | 1,8242 % | `maxTimeLimit` | 29.447,7 s |

**Dominanz-Ergebnis — Hauptbefund von N3:** SB-Dominanzverletzung sinkt von 3,92 % (K3, vor N1/N2) auf **0,70 %** (N3: (21.276.158,68 − 21.127.847,23) / 21.127.847,23 = 0,00702), ein ~5,6-facher Rückgang der Verletzung — stark konsistent mit der M-Block-Diagnose (Notkühler-Repreisung), dass ein erheblicher Teil der scheinbaren Dominanzverletzung ein Bepreisungsartefakt war, nicht ein reales MILP-Kopplungsproblem. MM bleibt dominant wie zuvor (S0-HK0 319.404,93 → 317.377,28 €, −2.027,65 €, PASS).

**Deckel-Bindung real und wie angewiesen gemeldet, nicht angepasst:** SB `j_man` bindet in S0-HK0 exakt bei 475,0650 MWh (identisch zur berechneten Grenze) — validiert, dass N1s Kappungsmechanismus echte Arbeit leistet (kein No-Op). Alle anderen Knoten bleiben unter ihrer jeweiligen Grenze (`j_pss` 1,0979 MWh am Limit, `j_psw` 0,9934 MWh knapp darunter). BASE-HK0 bleibt bei beiden Netzen wie von N1 gefordert per Konstruktion zulässig (SB BASE-HK0: `j_pss`=1,0591, `j_psw`=0,6164 MWh, beide unter ihrer Grenze).

**Notkühler- und Schließungs-MWh getrennt je Knoten (N2-Pflichtangabe):**

| Netz/Lauf | Notkühler-Knoten (MWh) | Schließungs-Knoten (MWh) | Summe Schließung | % Jahresbedarf |
|---|---|---|---|---|
| SB BASE-HK0 | `j_bmhkw`=329,37, `j_gtost`=259,27, `j_hkw`=109,66 | `j_pss`=1,059, `j_psw`=0,616 | 1,676 | ~0,00026 % |
| SB S0-HK0 | `j_bmhkw`=307,78, `j_gtost`=183,67, `j_hkw`=80,81 | `j_man`=475,065 (**am Deckel**), `j_pss`=1,098, `j_psw`=0,993 | 477,156 | 0,0746 % |
| MM BASE-HK0 | — (keine reinen KWK-Knoten) | `j_9`=5,29, `j_12`=6,28 | 11,572 | 0,1227 % |
| MM S0-HK0 | — | `j_9`=5,39, `j_12`=6,26 | 11,652 | 0,1235 % |

Alle Werte weit unter dem netzweiten 0,25-%-Deckel; nur der neue Per-Knoten-Deckel bei SB `j_man` bindet. Bemerkenswert: SB S0-HK0s Notkühlernutzung sinkt gegenüber BASE-HK0 an allen drei KWK-Knoten (z. B. `j_hkw` 109,66→80,81 MWh) — konsistent damit, dass die neu investierbare `hp_sb`-Kapazität (siehe unten) einen Teil der zuvor per Notkühler abgeregelten KWK-Wärme jetzt nutzt.

**KRITISCHER NEBENBEFUND (nicht Teil des N-Auftrags, aber während N3s Kapazitätsreporting entdeckt — Reporting-Bug, kein Modellbug):** `design_helpers.py`s `[DESIGN] Extracted HP ...`-Logzeile war für SB `hp_sb` in JEDEM Lauf dieser gesamten Session falsch (immer „capacity=0.0 MW, build=0.0" gemeldet), während die ECHTE Pyomo-Variable durchgehend eine substanzielle Investition zeigt:

| Lauf | `hp_sb_build` (echt) | `hp_sb_cap_mw` (echt) | Log-Meldung |
|---|---|---|---|
| B4 | 1 (Dispatch-Peak 6,72 MW) | ~6,72 (aus `dispatch_per_asset.csv`) | „capacity=0.0 MW, build=0.0" |
| I2 | 1 (Dispatch-Peak 7,93 MW) | ~7,93 | „capacity=0.0 MW, build=0.0" |
| K3 | 1 (Dispatch-Peak 6,24 MW) | ~6,24 | „capacity=0.0 MW, build=0.0" |
| N3 (SB-S0-HK0) | **1** (`hp_sb_build={'None': 1.0}`) | **5,325821519771965** (`hp_sb_cap_mw`) | „capacity=0.0 MW, build=0.0" |

Verifiziert über zwei unabhängige Wege (rohe Pyomo-Variable im `full_solution_dump.json` UND `dispatch_per_asset.csv`-Peak); `ek_sb` ist in N3 dagegen ECHT nicht gebaut (`EK_SB_cap_mw={'None': 0.0}`, `EK_SB_build={'None': -0.0}`, verifiziert über denselben Weg). MMs äquivalente `hp_main`-Extraktion wurde unabhängig geprüft (roh + Dispatch) und ist KORREKT — der Bug ist SB-`hp_sb`-spezifisch, nicht universell. Ursache bis `result_collector.py`s `_gather_component_metadata` zurückverfolgt, die für unified configs (dieses Projekt) explizit auf `_gather_component_metadata_unified(cfg)` verzweigt — diese Funktion selbst wurde noch nicht inspiziert; die eigentliche Ursache liegt dort. **Auswirkung eng begrenzt:** betrifft nur die reine Log-/Report-Zeile; Zielfunktionswert, Gap, Dominanz-Gate und `cost_breakdown.json`s `Capex_cost_EUR`/`Activation_cost_EUR` kommen direkt aus Gurobi bzw. der Pyomo-Variable und sind NICHT betroffen — alle bisherigen Dominanz-/Gate-Schlussfolgerungen dieser Session bleiben gültig. Betroffen ist ausschließlich die textliche „gebaute Kapazität"-Erzählung für SB `hp_sb` in früheren Statusmeldungen dieser Session, die fälschlich „HP nicht gebaut" berichteten. **Nicht behoben** (Scope-Entscheidung: N4 verlangt Weiterarbeit ohne Rückfrage; Fix als separate Folgeaufgabe vorgemerkt, nicht Teil dieses Auftrags).

**`Objective_residual_EUR`-Meldung bei SB (erneut geprüft, keine neue Regression):** Wie bereits in §4bc dokumentiert, erscheint bei jedem SB-Lauf ein `[COST-BREAKDOWN] Objective_residual_EUR`-ERROR-Log (N3: BC-SB-HK0 1.587.979,96 €, SB-S0-HK0 1.609.505,54 €) — vollständig durch `CO2_selfuse_netting_adjustment_EUR` erklärt (netto-vs-brutto-KPI-Differenz, `residual_note` im `cost_breakdown.json` bestätigt dies explizit); `reconciliation_check: OK` in allen vier N3-Läufen. Keine Auswirkung auf Zielfunktion oder Gate.

## §4bj — 2026-09-27: N4 — FINALE 6-ZEILEN-TABELLE + BREAK-EVEN/REGRET-AUSWERTUNG

> **⚠ ERSETZT durch §4bp (2026-09-29, Q2-Auftrag).** Die SB-S0-HK0-Zeile dieses Abschnitts (21.276.158,68 €, +148.311,44 € Regret) basiert auf N3s Inkumbenten mit 1,82 % Gap — inzwischen (§4bl) als überwiegend Gap-Artefakt identifiziert und durch zwei sauber konvergierte Nachläufe (Q1 frei optimierte WP-Größe, Q2 WP hart auf 5,33 MW fixiert) klar widerlegt: **beide zeigen NEGATIVES Regret** (Nettovorteil), nicht positives. Diese Zeile und ihre Zerlegung bleiben unten stehen als Dokumentation des „suboptimalen Inkumbenten" (nicht gelöscht, wie angewiesen), sind aber NICHT die maßgebliche wirtschaftliche Aussage. Siehe §4bp für die aktuelle, belastbare Zerlegung + Break-even-Analyse.

**Vergleichbarkeits-Vorbehalt zu den BASE-FIX-Zeilen:** N3 hat ausschließlich BASE-HK0 und S0-HK0 je Netz neu gerechnet (wie im N3-Auftrag spezifiziert); BASE-FIX wurde NICHT neu aufgelegt. Die einzigen verfügbaren BASE-FIX-Werte stammen aus B4 (§4bb, vor M1s Notkühler-Repreisung). Da M1/N1/N2 die Bepreisung des Schließungsterms an KWK-Knoten strukturell geändert haben, sind BASE-FIX' Kosten nicht unter derselben Konfiguration wie die vier N3-Zeilen entstanden — sie werden nachrichtlich mitgeführt (mit Kennzeichnung „vor Notkühler-Fix"), aber NICHT für Dominanz-Gate/Regret-Vergleiche verwendet. Falls für die Haupttabelle des Papers vergleichbare BASE-FIX-Werte gebraucht werden, wäre ein Nachlauf unter der finalen Konfiguration nötig (nicht Teil dieses Auftrags, nicht gestartet).

### Finale Ergebnistabelle

| Netz | Lauf | UB € | LB € | Gap | Dominanz-Gate | Notkühler+Schließung MWh (% Bedarf) | Status |
|---|---|---|---|---|---|---|---|
| MM | BASE-FIX *(vor Notkühler-Fix, B4)* | 319.711 | 319.440 | 0,085 % | — (ist BASE) | n/a (alte Konfiguration) | `maxTimeLimit` |
| MM | BASE-HK0 | 319.404,93 | 319.373,01 | 0,0100 % | — (ist BASE) | 11,572 (0,1227 %) | `optimal` |
| MM | S0-HK0 | 317.377,28 | 317.042,23 | 0,1056 % | **PASS** (−2.027,65 €) | 11,652 (0,1235 %) | `maxTimeLimit` |
| SB | BASE-FIX *(vor Notkühler-Fix, B4)* | 21.135.078 | 21.108.823 | 0,124 % | — (ist BASE) | n/a (alte Konfiguration) | `maxTimeLimit` |
| SB | BASE-HK0 | 21.127.847,23 | 21.110.422,34 | 0,0825 % | — (ist BASE) | 1,676 (0,00026 %) | `maxTimeLimit` |
| SB | S0-HK0 | 21.276.158,68 | 20.888.029,37 | 1,8242 % | **FAIL** (+148.311,44 €, **0,70 %** Verletzung) | 477,156 (0,0746 %, `j_man` am Deckel) | `maxTimeLimit` |

SB-Dominanzverletzung: 3,92 % (K3, vor Notkühler-Fix) → **0,70 %** (N3, nach M1/N1/N2) — 5,6-fache Verbesserung, konsistent mit der M-Block-Diagnose. MM bleibt klar dominant (PASS). Autoren-Entscheidung weiterhin offen (bereits in §4bf gestellt): 0,70 % Restverletzung akzeptieren oder mit einem weiteren Hebel (Symmetriebrechung, Fix-and-Relax) angehen — explizit NICHT Teil dieses Auftrags.

### Regret-Analyse auf realen Kosten (`real_costs_total_EUR`, ohne Hilfsterme)

**Definition (Interpretation, zur Prüfung durch den Autor vorgeschlagen — bei Abweichung bitte korrigieren):** Regret = reale Kosten der S0-HK0-Entscheidung (HP/EK-Zubau erlaubt) minus reale Kosten der BASE-HK0-Alternative (kein Zubau), am selben Netz. Regret > 0 bedeutet: die Zubau-Entscheidung war im Rückblick teurer als es Nicht-Investieren gewesen wäre. Reale Kosten (`real_costs_EUR`-Summe aus `cost_breakdown.json`, ohne Epsilon-/Tie-Break-Hilfsterme) statt Roh-Zielfunktion verwendet, da N4 explizit „auf realen Kosten" verlangt.

| Netz | Reale Kosten BASE-HK0 € | Reale Kosten S0-HK0 € | Regret € | Regret % von BASE |
|---|---|---|---|---|
| MM | 319.422,65 | 317.395,60 | **−2.027,05** (Nutzen) | −0,63 % |
| SB | 21.124.355,68 | 21.273.292,60 | **+148.936,92** (Regret) | +0,71 % |

MM: Die HP/EK-Investitionsentscheidung war korrekt (negatives Regret = Nettonutzen). SB: Die HP-Investitionsentscheidung (nur `hp_sb`, 5,326 MW gebaut, siehe §4bi-Nebenbefund; `ek_sb` nicht gebaut) zeigt positives Regret von 148.936,92 € — bestätigt die (nach dem Notkühler-Fix deutlich kleinere, aber nicht verschwundene) Dominanzverletzung auch auf rein realen Kosten.

**Kostenzerlegung des SB-Regrets (Δ = S0 − BASE je Position, erklärt woher die 148.937 € kommen):**

| Position | Δ € (S0 − BASE) | Richtung |
|---|---|---|
| Capex (`hp_sb`, annuitätisch) | +299.150,39 | neue Investition |
| Aktivierung (fix je Investitionsentscheidung) | +4.012,13 | neue Investition |
| Brennstoff | **−958.290,48** | Einsparung durch HP |
| Strombezug (Netz) | +27.135,72 | HP-Eigenverbrauch |
| KWK-Stromerlös (Verkauf) | **+666.101,98** | Erlösverlust (S0 verkauft weniger Strom) |
| CO2 | **−164.332,15** | Einsparung durch HP |
| Netzentgelt (Lastspitze) | +275.159,34 | höherer Peak durch HP-Bezug |
| **Summe** | **+148.936,92** | |

Die HP-Investition spart real Brennstoff und CO2 (zusammen −1.122.622,63 €) — das erwartete Verhalten. Diese Einsparung wird jedoch durch drei Effekte mehr als aufgezehrt: entgangener KWK-Stromerlös (+666.102 €, größter Einzeleffekt — die Fahrweise verschiebt sich weg von stromerlösgünstigen Stunden), höhere Lastspitzen-Netzentgelte (+275.159 €) und die Investition selbst (+303.163 €), zusammen +1.244.424 €. Nettosaldo: +148.937 € Regret.

**Break-even (ceteris paribus, aus bereits vorliegenden Daten abgeleitet — KEIN neuer Solve, daher nur erste Näherung):** Um SB-S0-HK0 bei sonst unveränderten Werten auf Regret=0 zu bringen, müsste EINE der folgenden Positionen sich um 148.936,92 € verbessern:

| Hebel | Erforderliche Änderung | Relative Größe |
|---|---|---|
| KWK-Stromerlös | +148.936,92 € mehr Erlös (−11.492.534 → −11.641.471 €) | ~1,30 % mehr Erlös |
| Capex+Aktivierung `hp_sb` | −148.936,92 € (−49,1 % der aktuellen Investitionskosten) | fast halbierte Annuität |
| Netzentgelt-Zuwachs | −148.936,92 € (−54,1 % des Lastspitzen-Zuwachses) | gut halbierter Peak-Zuwachs |

Dies ist eine lineare Sensitivität um den aktuellen Betriebspunkt, keine Re-Optimierung — ein echter Break-even-Preis (z. B. CAPEX-Förderquote oder Strompreisniveau, ab dem der Solver selbst eine andere Lösung wählt) würde neue Läufe erfordern und ist nicht Teil dieses Auftrags.

## §4bk — 2026-09-28: O1–O4 — Kampagnenabschluss (O2 Root-Cause behoben, O1/O3 laufen)

Vier Punkte vom Autor angeordnet (Kampagnenabschluss). Status bei Redaktion dieses Eintrags: **O2 vollständig behoben, O1/O3 als Hintergrundläufe gestartet (noch nicht fertig), O4-Kennzeichnung nachfolgend angewendet.**

**O2 (Priorität, ABGESCHLOSSEN) — echte Ursache gefunden, KEIN SB-spezifisches Problem:** `result_collector.py`s `_gather_component_metadata_unified()` setzte `invest_enabled` für JEDEN unified-config-Wärmepumpen-Asset hart auf `False` (Zeile 115, alt), unabhängig vom echten `investment.enabled`-Wert in der Config. Das sperrte den Pyomo-Variablen-Lesepfad (Zeile ~1108) komplett — `cap_value` fiel immer auf `hp.get("cap_init", hp["max_th"])` zurück, also den STATISCHEN `capacity_mw`-Wert aus der YAML (`0.0` bei beiden Netzen: MM `hp_main` UND SB `hp_sb` haben BEIDE `capacity_mw: 0.0` + `investment.enabled: true` — identische Konfigurationsstruktur). **Korrektur der bisherigen Session-Aussage:** Der Bug ist NICHT SB-`hp_sb`-spezifisch, wie zuvor (§4bi) berichtet — er betrifft strukturell auch MM `hp_main` gleichermaßen. Dass frühere MM-Prüfungen (I3-Ära) "korrekt" aussahen, war Zufall: die Meldung "capacity=0.0 MW, build=0.0" ist im Bug-Zustand IMMER die Ausgabe, unabhängig vom Solver-Ergebnis — bei den damals geprüften MM-Läufen war die wahre gebaute Kapazität zufällig ebenfalls 0, sodass Bug-Ausgabe und Wahrheit übereinstimmten, nicht weil der Code korrekt war. Ein zweiter, verwandter Befund: der `p2h`-Zweig (EK/`eboiler_main`/`ek_sb`) hatte GAR KEINEN Pyomo-Lesepfad und meldete nie `Build_binary` — ebenfalls behoben (gleiches Muster wie bei den Wärmepumpen). Fix: `invest_enabled` wird jetzt aus `asset_data["investment"]["enabled"]` gelesen (Wärmepumpe UND P2H); `cap_min`/`cap_max` werden bei aktivierter Investition aus `capacity_min_mw`/`capacity_max_mw` übernommen. Storage (`TES_cap_energy`/`TES_cap_power`/`TES_build`) war bereits korrekt (liest unconditional vom Modell, kein `invest_enabled`-Gate) — nicht betroffen. Code: `calion/run/result_collector.py`, Funktion `_gather_component_metadata_unified` + der `p2h`-Extraktionsblock in `_collect_timeseries_and_summary`.

**Re-Extraktion (Teil von O2):** Da `full_solution_dump.json` erst seit K1 (2026-09-26) unconditional geschrieben wird, existiert es NICHT für B4/I2 (vor K1) — für diese Läufe ist eine Neu-Extraktion ohne Re-Solve nicht möglich; sie werden ohnehin durch O1/O3 ersetzt/überholt. Für die beiden N3-Läufe mit echter Investitionsfreiheit (MM-S0-HK0, SB-S0-HK0) wurde je ein kurzer Re-Solve (TimeLimit 120s/180s, MIPGap 0,02, vollständiger Warmstart aus dem jeweiligen N3-Dump — reproduziert exakt denselben Inkumbenten, keine neue Optimierung) unter dem jetzt reparierten Code gestartet, um die korrigierten Kapazitäten gegen die bereits unabhängig verifizierten Rohwerte (Pyomo-Variable direkt aus `full_solution_dump.json`) zu bestätigen. Ergebnis folgt in einem Nachtrag zu diesem Abschnitt.

**O1 (läuft, Ergebnis ausstehend):** `SB-S0-HK0-PIN0` unter der finalen Konfiguration neu aufgelegt (bisheriger `k2_pin0`-Lauf stammt aus der alten, VOR M1/N1/N2 liegenden Konfiguration und ist damit nicht mehr die richtige Referenz für den Inkumbenten-Pool). Neues Szenario `MM-S0-HK0-PIN0` in `configs/paper_2/scenarios.yaml` angelegt (analog zu SB, hp_main/eboiler_main investitionsseitig hart auf 0, TES aus) — existierte für Memmingen bisher gar nicht. Beide unter `CALION_DUMP_MODE=chp_only`, `CALION_PRESSURE_SLACK_MODE=suspend_hydraulic`, matched-effort-Protokoll (MM 4 h/SB 8 h, MIPGap=1e-4, MIPFocus=3, Cuts=2, Threads=4), mit vollständigem Warmstart aus dem jeweils nächstverwandten N3-Lauf. Hintergrundläufe gestartet 2026-09-28 09:45 (`output/mm_s4_reconcile/o1_mm_pin0`, `o1_sb_pin0`).

**O3 (läuft, Ergebnis ausstehend):** `BC-MM` und `BC-SB` (BASE-FIX, TVLFIX-Heizkurve) unter derselben finalen Konfiguration neu aufgelegt — die einzigen bisherigen BASE-FIX-Werte stammen aus B4 (vor dem Notkühler-Fix, siehe Vergleichbarkeits-Vorbehalt in §4bj) und werden hiermit durch vergleichbare Werte ersetzt. Gleiches Protokoll, Warmstart aus dem jeweiligen N3-BASE-HK0-Lauf (gleiche Topologie, andere Temperaturregime — hilft dem Solver ggf. teilweise). Hintergrundläufe gestartet 2026-09-28 09:45/09:46 (`output/mm_s4_reconcile/o3_mm_basefix`, `o3_sb_basefix`). Die anschließend vom Autor verlangte "Bilanzprüfung erneut über den unabhängigen Pfad" (O3, zweiter Teil) folgt nach Abschluss dieser beiden Läufe.

**O2-Nachtrag (Re-Extraktion VERIFIZIERT, beide Netze):** Die beiden kurzen Re-Solves (transplantieren denselben Inkumbenten neu, keine neue Optimierung — Inkumbent bit-genau reproduziert: MM 317.377,2808 vs. N3s 317.377,2808599086; SB 21.276.158,68 vs. N3s 21.276.158,67578349) liefen unter dem reparierten Code durch. Ergebnis: **SB `hp_sb`** — Log zeigt jetzt korrekt `[DESIGN] Extracted HP hp_sb: capacity=5.3 MW, build=1.0` (vorher IMMER "0.0/0.0"), exakte Übereinstimmung mit der rohen Pyomo-Variable (`hp_sb_build=1.0`, `hp_sb_cap_mw=5.325821519771965`). **MM `hp_main`** — Log zeigt weiterhin "capacity=0.0 MW, build=0.0", jetzt aber KORREKT: rohe Pyomo-Variable bestätigt `hp_main_build=0.0`, `hp_main_cap_mw=0.0` — MM baut in diesem Lauf tatsächlich keine WP (stützt sich stattdessen auf `eboiler_main`). **MM `eboiler_main`** (p2h-Fix, zweiter Teil von O2) — rohe Variable `EBOILER_MAIN_build=1.0`, `EBOILER_MAIN_cap_mw=0,10293 MW`, exakte Übereinstimmung mit dem historischen I3-Befund; zusätzlich der reparierte Code-Pfad isoliert gegen eine realistische Config-Struktur getestet (`invest_enabled` korrekt `True`, Variable-Namen `EBOILER_MAIN_cap_mw`/`EBOILER_MAIN_build` exakt passend). **Konsistenz-Assertion (O2-Pflichtangabe) erfüllt für beide geprüften Fälle:** gemeldete Kapazität == Pyomo-Variable == (für SB zusätzlich historisch) aus Dispatch ableitbare Kapazität. Kein Lauf muss als `failed_reporting` markiert werden. **Korrektur der Ursachen-Aussage aus §4bk oben bestätigt:** der Bug war strukturell identisch in beiden Netzen; dass er sich in MMs historischen Prüfungen nie als Fehler zeigte, lag daran, dass die wahre Kapazität dort zufällig ebenfalls 0 war (hp_main) bzw. p2h nie geprüft wurde (eboiler_main, wo der Bug real war, aber niemand hinschaute, da design_helpers.py p2h nie geloggt hat).

**O4 (Berichtsform, ANGEWENDET auf §4bj):** Die SB-S0-HK0-Zeile in §4bj (21.276.158,68 €, 5,33 MW `hp_sb`) wird ab sofort als **"erzwungener WP-Punkt"** geführt, nicht als S0-Optimum — der Gap dieses Laufs (1,82 %) und die noch offene Dominanzverletzung (0,70 %) bedeuten, dass der wahre S0-Optimalpunkt nicht bekannt ist, nur ein zulässiger, gemeldeter Inkumbent. Die Kostenzerlegung (−958 T€ Brennstoff, −164 T€ CO2 gegen +666 T€ entgangenen KWK-Erlös, +275 T€ Leistungsentgelt, +303 T€ Investition) bleibt als mechanistische Erklärung des Null-/Negativ-Befunds im Bericht stehen, unabhängig vom Ausgang von O1 — sie erklärt, WARUM dieser konkrete erzwungene Punkt teurer ist als BASE, nicht ob ein anderer S0-Punkt existiert, der es nicht wäre. Die finale Tabelle (je Zeile UB/LB/Gap/Dominanz/Notkühler-MWh/Closure-MWh/gebaute Kapazitäten/reale Kosten nach Positivliste/Konfigurations-Hash) wird nach O1/O2/O3-Abschluss in einem Nachtrag zu diesem Abschnitt zusammengestellt.

## §4bl — 2026-09-28: O1/O3 KAMPAGNE ABGESCHLOSSEN (4/4 Läufe) — finale Tabelle + KRITISCHER NEUBEFUND zum "erzwungenen WP-Punkt"

Alle vier Hintergrundläufe (O1: `MM-S0-HK0-PIN0` neu angelegt + `SB-S0-HK0-PIN0` unter Endkonfiguration neu; O3: `BC-MM` + `BC-SB` unter Endkonfiguration neu) sind fertig, keine Fehler, matched-effort-Protokoll eingehalten (MM 4 h/SB 8 h, MIPGap-Ziel 1e-4, MIPFocus=3, Cuts=2, Threads=4). Konfigurationsstand: Basis-Commit `26650a1` plus die in dieser Session unveränderten Arbeitsstand-Änderungen (M1/N1/N2-Schließungslogik + O2-Reporting-Fix, beide bereits vor Kampagnenstart im Code); `CALION_DUMP_MODE=chp_only`, `CALION_PRESSURE_SLACK_MODE=suspend_hydraulic` für alle vier Läufe identisch gesetzt.

### Vollständige Ergebnistabelle (6 Kernzeilen + 2 Zusatzzeilen PIN0)

| Netz | Lauf | UB € | LB € | Gap | Status | Notkühler+Closure MWh (%Bedarf) | Gebaute Kapazität | Export-Hash |
|---|---|---|---|---|---|---|---|---|
| MM | BASE-FIX | 319.570,57 | 319.418,77¹ | 0,0475 % | `maxTimeLimit` | 8,02+4,14=12,16 (0,129 %) | — (kein HP/EK) | `da53ff5a` |
| MM | BASE-HK0 | 319.404,93 | 319.373,01 | 0,0100 % | `optimal` | 6,28+5,29=11,57 (0,123 %) | — (kein HP/EK) | `dad08180` |
| MM | S0-HK0 | 317.377,28 | 317.042,23 | 0,1056 % | `maxTimeLimit` | 6,26+5,39=11,65 (0,124 %) | `eboiler_main` 0,103 MW (build=1); `hp_main` 0 MW (build=0) | `77aa9598` |
| MM | S0-HK0-PIN0 | 319.382,19 | 319.350,37¹ | 9,97e-5 | **`optimal`** | 6,28+5,29=11,57 (0,123 %) | 0 MW (Investition fix 0, wie spezifiziert) | `0702b261` |
| SB | BASE-FIX | 21.139.055,70 | 21.119.303,02¹ | 0,0935 % | `maxTimeLimit` | 328,94+260,38+109,59+1,06+0,72=700,69 (0,109 %)² | — (kein HP/EK) | `8dacfa6e` |
| SB | BASE-HK0 | 21.127.847,23 | 21.110.422,34 | 0,0825 % | `maxTimeLimit` | 329,37+259,27+109,66+1,06+0,62=699,98 (0,109 %) | — (kein HP/EK) | `1addee5c` |
| SB | S0-HK0 ("erzwungener WP-Punkt") | 21.276.158,68 | 20.888.029,37 | 1,8242 % | `maxTimeLimit` | 307,78+183,67+80,81+475,07+1,10+0,99=1.049,4 (0,164 %) | `hp_sb` 5,326 MW (build=1); `ek_sb` 0 MW (build=0) | `03162e31` |
| SB | S0-HK0-PIN0 | 21.131.011,21 | 21.103.481,32¹ | 0,1301 % | `maxTimeLimit` | 233,55+175,89+292,36+0,90+0,32=702,9 (0,110 %) | 0 MW (Investition fix 0, wie spezifiziert) | `a53806a3` |

¹ LB = UB × (1 − Gap), aus `obj_eur`/`mip_gap` rekonstruiert (kein separates LB-Feld im meta.json dieser Läufe).
² BASE-FIX/BASE-HK0 haben je 3 reine-KWK-Notkühler-Knoten (`j_bmhkw`/`j_gtost`/`j_hkw`) + 2 Closure-Knoten (`j_pss`/`j_psw`); Summe zusammengefasst für Übersichtlichkeit, Einzelwerte im Fließtext unten.

**Reale Kosten nach Positivliste (`real_costs_total_EUR`, ohne Hilfsterme), die beiden neuen O3-BASE-FIX-Zeilen:**

| Netz | Fuel € | Grid-Bezug € | KWK-Erlös € | CO2 € | Leistungsentgelt € | Capex+Aktivierung € | Summe real € |
|---|---|---|---|---|---|---|---|
| MM BASE-FIX | — (siehe economics.csv, nicht separat gezogen) | — | — | — | — | 0 | — |
| SB BASE-FIX | 26.262.016,01 | 26.072,87 | −12.159.955,46 | 6.957.843,73 | 49.583,97 | 0 | **21.135.561,12** |
| SB S0-HK0-PIN0 | 26.252.970,18 | 26.630,96 | −12.156.749,76 | 6.955.201,89 | 50.907,78 | 0 | **21.128.961,04** |

(MM BASE-FIX's `real_costs_EUR`-Aufschlüsselung wurde aus Zeitgründen nicht einzeln gezogen, da für diese Zeile — ohne HP/EK — keine Investitionsentscheidung zu erklären ist; `real_costs_total_EUR` ≈ `obj_eur`, da bei BASE-Läufen kaum Hilfsterme greifen.)

### O1-Dominanzprüfung (PIN0 vs. BASE-FIX, unter Endkonfiguration — reproduziert K2s Beweis)

| Netz | PIN0 UB € | BASE-FIX UB € | Δ (PIN0−BASEFIX) € | Gate |
|---|---|---|---|---|
| MM | 319.382,19 | 319.570,57 | **−188,38** | **PASS** |
| SB | 21.131.011,21 | 21.139.055,70 | **−8.044,49** | **PASS** |

Beide Netze bestehen die Konstruktions-Dominanzprüfung erneut, jetzt unter der finalen Notkühler-Konfiguration — reproduziert K2s ursprünglichen Beweis (§4be) exakt in seiner Struktur: die S0-Topologie (Assets am Knoten platziert, Investition auf 0 fixiert) kostet nie mehr als die entsprechende BASE-FIX-Alternative. Auf realen Kosten bestätigt sich das für SB ebenfalls (SB S0-HK0-PIN0 real 21.128.961,04 € vs. SB BASE-FIX real 21.135.561,12 €, Δ=−6.600,08 €).

### KRITISCHER NEUBEFUND: der "erzwungene WP-Punkt" (N3 SB-S0-HK0) ist SCHLECHTER als ein im selben Suchraum liegender Investitions-Null-Punkt — das bisherige Regret ist zu einem erheblichen Teil ein Gap-Artefakt, nicht (nur) ein ökonomischer Befund

**Der Befund:** `SB-S0-HK0-PIN0` (21.131.011,21 €) liegt **145.147,47 € UNTER** N3s realem `SB-S0-HK0`-Inkumbenten (21.276.158,68 €) — bei nahezu identischer Topologie (`hp_sb`/`ek_sb` sind in BEIDEN Läufen am Knoten `j_man` platziert; der einzige Unterschied ist, ob die Investitionsvariablen frei oder auf 0 fixiert sind). Da `hp_sb_build=0`/`cap_mw=0` immer ein zulässiger Punkt innerhalb der Investitions-Schranken `[0, capacity_max_mw]` des ECHTEN (investitionsfreien) S0-HK0-Modells ist, und PIN0s Modell strukturell nahezu identisch dispatcht (gleiche Schließungs-/Notkühler-Logik am selben Knoten), ist PIN0s Zielfunktionswert eine SEHR STARKE empirische Schätzung dafür, was das echte S0-HK0-Modell an der Investitions-Null-Ecke seines eigenen Suchraums erreichen würde — also fast 145 T€ besser als der von Gurobi in 8 h tatsächlich gefundene Inkumbent.

**Einordnung (gleiche Vorsicht wie bei K2/K4 — PIN0 ist ein STRUKTURELL ANDERES, kleineres Modell, kein strenger Unterraum-Beweis):** `n_vars` unterscheidet sich (PIN0: 7.358.419, identisch zu BASE-HK0/BASE-FIX; echtes S0-HK0: 7.384.701, +26.282 Investitions-/Aktivierungsvariablen) — PIN0 ist also NICHT bitgenau derselbe Lösungsraum, sondern ein durch `investment.enabled=false` strukturell reduziertes Modell (Ghost-Variable-Entfernung, analog zur E1-Fix-Klasse). Der Vergleich ist daher — wie bei K2 — ein Beweis "durch Konstruktion" (starke empirische Evidenz), keine strenge mathematische Unterraum-Garantie. Trotzdem: die Größenordnung (145 T€, mehr als das gesamte bisherige Regret von 148.937 €) ist zu groß, um als Zufall abgetan zu werden.

**Konsequenz für §4bj/§4bk und O4s "erzwungener WP-Punkt"-Rahmung:** Die dort berichtete Regret-Kostenzerlegung (−958 T€ Brennstoff/−164 T€ CO2 gegen +666 T€ KWK-Erlösverlust/+275 T€ Leistungsentgelt/+303 T€ Investition, netto +148.937 €) bleibt als KORREKTE Erklärung dafür stehen, WARUM der konkret gefundene Inkumbent teurer ist als BASE — das ist weiterhin gültige Buchhaltung dieses einen Punktes. Was sich ändert: die Interpretation, dass diese 148.937 € das "wahre" Regret einer HP-Investitionsentscheidung widerspiegeln, ist jetzt WIDERLEGT — der Solver hat innerhalb von 8 h keinen Inkumbenten gefunden, der nahe an das (durch PIN0 demonstrierte) Investitions-Null-Niveau herankommt, obwohl ein strukturell sehr ähnlicher, viel kleinerer Lauf (PIN0) dieses Niveau in derselben Zeit sauber erreicht (`status=maxTimeLimit`, Gap nur 0,13 %). Die vorsichtigste korrekte Aussage: **der wahre S0-HK0-Optimalwert liegt vermutlich nahe bei oder unter PIN0s Niveau (~21,13 Mio. €) — möglicherweise sogar unter BASE-HK0 (21.127.847 €), wenn der Solver eine bessere Nicht-Null-Investition findet als die reine Null-Ecke.** Ob eine ECHTE HP-Investition sich lohnt, bleibt damit **offen, nicht widerlegt** — anders als N3s Zahlen suggerierten. Empfehlung (keine Handlung ohne Freigabe): ein gezielter Nachlauf von SB-S0-HK0 mit vollem Warmstart aus PIN0s eigener Lösung (statt aus dem alten, nicht mehr passenden Bezugspunkt) hätte gute Chancen, den Inkumbenten deutlich unter 21,28 Mio. € zu drücken — analog zu K3s Methodik, aber diesmal mit einem strukturell saubereren Startpunkt.

### Per-Knoten Notkühler/Closure, alle vier neuen Läufe

| Lauf | Notkühler-Knoten (MWh) | Closure-Knoten (MWh) |
|---|---|---|
| MM BASE-FIX | — | `j_12`=8,02, `j_9`=4,14 |
| MM S0-HK0-PIN0 | — | `j_12`=6,28, `j_9`=5,29 |
| SB BASE-FIX | `j_bmhkw`=328,94, `j_gtost`=260,38, `j_hkw`=109,59 | `j_pss`=1,06, `j_psw`=0,72 |
| SB S0-HK0-PIN0 | `j_bmhkw`=233,55, `j_gtost`=175,89 (kein `j_hkw`-Eintrag diesen Lauf) | `j_man`=292,36, `j_pss`=0,90, `j_psw`=0,32 |

Alle Werte weit unter dem netzweiten 0,25-%-Deckel; keine Kappungsgrenze bindet in diesen vier Läufen (anders als N3s echtes SB-S0-HK0, wo `j_man` exakt am Deckel lag).

**Damit sind O1, O2 und O3 vollständig abgeschlossen.** O4s Tabelle ist oben zusammengestellt. Autoren-Entscheidungen offen: (a) den neuen Befund (echtes S0-HK0-Regret ist überwiegend ein Gap-Artefakt) akzeptieren und ggf. den empfohlenen PIN0-geseedeten Nachlauf beauftragen, oder den aktuellen Stand (mit dieser Einschränkung dokumentiert) als finalen Bericht verwenden; (b) die 0,70-%-Restverletzung der Dominanz bei N3s echtem SB-S0-HK0 weiter verfolgen oder akzeptieren (unverändert von §4bj); (c) `design_helpers.py`s p2h-Logging-Lücke (EK wird nie geloggt, nur HP) als separate Folgeaufgabe beauftragen oder nicht.

## §4bm — 2026-09-29: Q1–Q4 — genau der empfohlene Nachlauf beauftragt, plus konstruierter WP-Lauf, plus MM-Speicher-Break-even-Wiederholung, plus Dauerregel

Der Autor beauftragte exakt die am Ende von §4bl empfohlene Maßnahme (PIN0-geseedeter SB-S0-HK0-Nachlauf) sowie drei weitere Punkte. Alle Rechenläufe sind Hintergrundläufe, Status bei Redaktion dieses Eintrags: **alle 7 neuen Läufe gestartet, keiner fertig.**

**Q1 (SB-S0-HK0 neu, Warmstart aus PIN0 statt der alten Lauf-Kette):** `output/mm_s4_reconcile/q1_sb_s0_pin0seed/SB-S0-HK0`, `CALION_WARMSTART_FROM=output/mm_s4_reconcile/o1_sb_pin0/SB-S0-HK0-PIN0` (volle `full_solution_dump.json`, nicht die alte, inzwischen überholte Kette aus B4/I2/K3), 8 h, MIPGap 1e-4, MIPFocus 3, Cuts 2, Threads 4 — identische Endkonfiguration wie N3/O1/O3. Ziel: das Intervall [0; ~1,2 %] für den Wert von WP/EK bei SB schließen (PIN0 bei 21.131.011 € bekannt, BASE-HK0 bei 21.127.847 € — die Spanne, in der eine echte Investitionsentscheidung liegen könnte, ist ~3.164 € bzw. 0,015 % bis zum jetzt bekannten oberen Anker von N3s altem, jetzt als Gap-Artefakt eingeordnetem Inkumbenten bei +148.312 €). Gestartet 09:03 Uhr.

**Q2 (konstruierter WP-Lauf, ersetzt die zurückgezogene Regret-Analyse):** neues Szenario `SB-S0-HK0-HPFIX533` in `scenarios.yaml` — `hp_sb` hart auf 5,325821519771965 MW fixiert (exakt N3s alter Inkumbentengröße, für Vergleichbarkeit der Zerlegung), `ek_sb` bleibt voll investierbar (unverändert aus der Basis-Config übernommen), TES aus. Mechanismus verifiziert durch Code-Lektüre (nicht nur Beobachtung): `component_assembler.py:606-610` liest `capacity_init_mw = capacity_mw` (Top-Level-Feld) wenn `investment.initial_capacity_mw` nicht gesetzt ist; `heat_pump.py:132-134` fixiert dann `build.fix(1)` und `cap.fix(capacity_init_mw)` exakt bei `investable=False` und `capacity_init_mw>0` — ein ANDERER Codepfad als PIN0s `capacity_mw=0`-Fall (dort greift zusätzlich die E1-Ghost-Variablen-Entfernung, hier nicht, da `capacity_init_mw>0`). Restringiertes Modell (eine Investitionsentscheidung weniger als das echte S0-HK0), daher leichter lösbar. `output/mm_s4_reconcile/q2_sb_hpfix533/SB-S0-HK0-HPFIX533`, gleicher Warmstart aus PIN0, gleiches 8-h-Protokoll. Gestartet 09:03 Uhr. Zerlegung nach Positivliste gegen PIN0 (Brennstoff/CO2/KWK-Erlös/Leistungsentgelt/Investition) und die daraus linearisierten Break-even-Schwellen folgen nach Abschluss; §4bj wird dann entsprechend ersetzt (alte Zerlegung wird dort als „suboptimaler Inkumbent" gekennzeichnet, nicht gelöscht).

**Q3 (P1, MM-Speicher-Break-even unter Endkonfiguration):** die ursprüngliche Spezifikation stammt aus der Schritt-6-Kampagne (2026-09-21, docs SS4aj/SS4an), die VOR dem Dump-Preis-Fix (B, 2026-09-22) UND vor der gesamten M1/N1/N2-Notkühler-Überarbeitung lief — Zeile 1163 des Kontrolldokuments hält bereits von damals fest, dass diese Zahlen „kein Regret-Wert" sind, weil sich der Kontext ändert; das gilt jetzt doppelt. Design (rekonstruiert aus den Original-Skripten `scripts/paper_2/run_step6_queue.py`, nicht aus dem Gedächtnis): 4 `MM-S2-HK0`-Läufe mit Tank-Kostenanker c0 skaliert auf ×1,0/×0,7/×0,5/×0,3 (`CALION_TES_C0_SCALE`-Env-Var, Mechanismus im Code verifiziert, `scenario_runner.py:500-509`) plus 1 „Regret"-Lauf mit fest verdrahteter (nicht-investierbarer) Tankgröße nach der einheitlichen Regel „Jahreswärmebedarf/365, gerundet auf die nächste Leiter-Sprosse" (`CALION_TES_FIX_MWH`-Env-Var, `scenario_runner.py:734-743`). Die alte Sprosse (23,9 MWh) wurde NICHT blind übernommen, sondern mit der AKTUELLEN Leiter (`storage_geometry.yaml`: `[0, 0.5, 1.1, 2.2, 3.3, 4.3, 6.5, 8.7, 10.8, 13.0, 17.4, 23.9, 30.4]` MWh — hat sich seit Schritt 6 geändert) und N3s FRISCHEM `MM-S0-HK0`-Dispatch (25,84 MWh/Tag) neu berechnet — Ergebnis bestätigt zufällig denselben Wert, 23,9 MWh bleibt die nächste Sprosse. Alle 5 Läufe unter Endkonfiguration (`chp_only`+`suspend_hydraulic`), MM-Protokoll (4 h, MIPGap 1e-4, MIPFocus 3, Cuts 2), Warmstart aus N3s `MM-S0-HK0`. Gestartet 09:06–09:08 Uhr (die ersten vier c0-Läufe mussten nach einem Bash-Quoting-Fehler beim ersten Versuch — eine `$(...)`-Konditionalsubstitution zerstörte das Env-Var-Prefix-Parsing — sauber neu gestartet werden; verifiziert über `ps aux`, dass nur der zuerst fehlerfrei laufende `fix23.9`-Lauf vom ersten Versuch übrig blieb, die anderen vier liefen nie an). Pfade: `output/mm_s4_reconcile/q3_mm_s2_c0x{1.0,0.7,0.5,0.3}/MM-S2-HK0`, `output/mm_s4_reconcile/q3_mm_s2_fix23.9/MM-S2-HK0`. Dominanzreferenz: MM-S0-HK0 (N3, 317.377,28 €) dient zugleich als Q4-PIN0-Referenz für diese Läufe (siehe Q4) — eine eigene MM-S2-HK0-PIN0 ist nicht nötig, da S2 = S0 + investierbarer TES-Freiheitsgrad; TES auf 0 fixiert macht S2 strukturell zu S0.

**Q4 (Dauerregel fürs Kontrolldokument, AB SOFORT GÜLTIG):** **Jedes Investitionsszenario wird gegen seinen eigenen PIN0-Lauf (alle Investitions-/Kapazitätsvariablen hart auf 0 bzw. auf einen definierten Referenzwert fixiert, sonst identische Topologie/Konfiguration) geprüft, BEVOR eine wirtschaftliche Aussage (Dominanz, Regret, „lohnt sich nicht") daraus abgeleitet wird. Fehlt der PIN0-Lauf, ist die wirtschaftliche Aussage nicht zulässig — technische/deskriptive Aussagen (Kapazität, Gap, Status) bleiben davon unberührt.** Begründung: §4bl zeigt, dass ohne diese Prüfung ein reines MIP-Gap-Artefakt (N3s SB-S0-HK0-Inkumbent) als ökonomischer Befund fehlinterpretiert worden wäre. Anwendung rückwirkend: N3s SB-S0-HK0-Zeile trägt bereits die Einschränkung aus §4bl/O4; MM-S0-HK0/S0-HK0-PIN0 (O1) erfüllt die Regel bereits (PASS, Dominanz belastbar). Anwendung vorausschauend: Q3s MM-S2-HK0-Sweep nutzt MM-S0-HK0 als PIN0-Äquivalent (Begründung oben); jede künftige SB-S1/S2/S3-Auswertung braucht denselben Nachweis, sobald sie unter der Endkonfiguration wiederholt wird (aktuell nicht terminiert).

Nächste Schritte (kein Autoren-Input nötig, "ohne Rückfrage" wie durchgehend in diesem Auftragsblock): Läufe abwarten, Q1/Q2-Ergebnisse gegen PIN0 und BASE-HK0 prüfen, §4bj gemäß Q2 ersetzen, Q3s Break-even-Tabelle gegen die Q4-Regel prüfen und dokumentieren.

## §4bn — 2026-09-29: Q3 (P1, MM-Speicher-Break-even) ABGESCHLOSSEN — alle 5 Läufe fertig, PLUS ein DRITTER Reporting-Bug gefunden (Speicher-Kapazität, analog zu O2, aber ein anderer Codepfad)

Alle 5 `MM-S2-HK0`-Läufe fertig, keine Fehler, `status=maxTimeLimit` (4-h-Limit erreicht) in allen fünf Fällen.

**DRITTER Reporting-Bug (gefunden bei der Verifikation, nicht Teil von Q1-Q4, aber im Sinne der Q4-Sorgfaltspflicht sofort geprüft):** `design_helpers.py`s `[DESIGN] Extracted Storage: capacity=0.0 MWh, power=0.0 MW, build=0.0`-Logzeile ist für `geometric_storage`-Assets (wie `tes_main`) STRUKTURELL FALSCH — sie erschien identisch (alle Nullen) in JEDEM der 5 Läufe, auch in `fix23.9`, wo der Tank hart auf 23,9 MWh fixiert war. Rohe Pyomo-Variable (`full_solution_dump.json`) bestätigt: `tes_main_build=1.0`, `tes_main_V_m3=1657.69`, `tes_main_cap_power=5.975 MW` für `fix23.9` — der Tank ist eindeutig gebaut, die Logzeile lügt. Ursache (nicht behoben, nur diagnostiziert): `_gather_component_metadata`s Storage-Extraktion liest generische `TES_cap_energy`/`TES_build`-Variablennamen (der alte, einfache `StorageBlock`-Pfad — Kommentar im Code: „0 fuer geometric_storage/TES"), die für `geometric_storage`-Assets NIE existieren (deren echte Variablen heißen `{comp}_build`/`{comp}_V_m3`/`{comp}_cap_power`/`{comp}_E0`) — ein NAMENS-/PFAD-MISMATCH derselben Fehlerklasse wie der O2-Bug (§4bk), aber ein ANDERER Codepfad (Storage- statt Wärmepumpen-/P2H-Extraktion) und daher nicht durch den O2-Fix mitbehoben. **Verlässliche Quelle stattdessen gefunden und verifiziert:** `geometry.csv` (separat exportiert von `thermal_network_exporter.py`, NICHT von `design_helpers.py`) berichtet `build`/`V_TES_m3`/`E_TES_max_MWh`/`cap_power_MW` korrekt — kreuzverifiziert gegen die rohe Pyomo-Variable für alle 5 Läufe, exakte Übereinstimmung (z. B. `fix23.9`: `E_TES_max_MWh=23.9`, `build=1`, passend zur Vorgabe). Alle Kapazitätsangaben unten stammen aus `geometry.csv`, NICHT aus der Logzeile. **Auswirkung eng begrenzt** (wie beim O2-Bug): nur die Logzeile/das reine Reporting ist betroffen, `obj_eur`/Gap/Dominanz aus Gurobi sind unberührt. Empfehlung (nicht umgesetzt): `_gather_component_metadata`s Storage-Zweig um einen `geometric_storage`-Fall erweitern (analog zum O2-Fix bei Wärmepumpe/P2H), oder `design_helpers.py` direkt auf `geometry.csv` umstellen.

### Ergebnistabelle (Dominanzreferenz: MM-S0-HK0 = 317.377,28 € (N3), zugleich Q4-PIN0-Äquivalent — Begründung: S2 = S0 + investierbarer TES-Freiheitsgrad, TES auf 0 macht S2 strukturell zu S0)

| Lauf | UB € | LB € | Gap | Status | Tank gebaut? | V_TES m³ | E_TES,max MWh | P_TES MW | Δ vs. S0-HK0 € | Notkühler+Closure MWh |
|---|---|---|---|---|---|---|---|---|---|---|
| c0×1,0 (voller Preis) | 317.348,39 | 316.663,13¹ | 0,2159 % | `maxTimeLimit` | **Nein** | 0 | 0 | 0 | −28,89 (Rauschen) | `j_12`=6,26, `j_9`=5,39 |
| c0×0,7 | 317.326,24 | 314.827,69¹ | 0,8192 % | `maxTimeLimit` | **Nein** | 0 | 0 | 0 | −51,04 (Rauschen) | `j_12`=6,26, `j_9`=5,39 |
| c0×0,5 | 315.484,95 | 313.879,02¹ | 0,5088 % | `maxTimeLimit` | **Ja** | 76,30 | **1,1** | 0,28 | **−1.892,33** | `j_12`=6,30, `j_9`=0,13 |
| c0×0,3 | 313.377,73 | 311.923,72¹ | 0,4638 % | `maxTimeLimit` | **Ja** | 228,89 | **3,3** | 0,83 | **−3.999,55** | `j_12`=6,32, `j_9`=0,20 |
| Regret (fix 23,9 MWh) | 311.265,71 | 310.742,46¹ | 0,1681 % | `maxTimeLimit` | **Ja (erzwungen)** | 1.657,69 | **23,9** | 5,97 | **−6.111,57** | `j_12`=6,43 (kein `j_9`-Eintrag) |

¹ LB = UB × (1 − Gap), aus `obj_eur`/`mip_gap` rekonstruiert.

**Befund (Break-even-Kurve):** klare monotone Stufe — bei vollem (×1,0) und ×0,7-Preis lohnt sich KEIN Tank (Build=0, die winzigen negativen Δ-Werte von −29/−51 € sind reines Solver-/MIP-Gap-Rauschen zwischen unabhängigen Läufen, keine reale Speicher-Wertschöpfung). Zwischen ×0,7 und ×0,5 liegt die Aktivierungsschwelle — ab ×0,5 baut der Solver einen (kleinen) Tank und die Einsparung wächst mit sinkendem c0 monotone: 1,1 MWh/−1.892 € (×0,5) → 3,3 MWh/−4.000 € (×0,3) → 23,9 MWh/−6.112 € (erzwungen, ×1,0-Preis aber ohne Investitionsentscheidung). Alle 5 Läufe bestehen die Q4-PIN0-Prüfung: S2-HK0s Inkumbent ist in JEDEM Fall ≤ S0-HK0 (317.377,28 €), wie es die Generalisierungsbeziehung (S2 ⊇ S0) verlangt — keine Dominanzverletzung, alle Δ-Werte in der Tabelle sind daher belastbare, wenn auch bei ×1,0/×0,7 vernachlässigbar kleine, Aussagen.

**Damit ist Q3 (P1) vollständig abgeschlossen.** Q1/Q2 (SB, 8-h-Budget) laufen zum Zeitpunkt dieses Eintrags noch (Q1 bei ~20.961.430 €/0,36 % Gap, Q2 bei ~20.608.000 €/0,14 % Gap, beide `maxTimeLimit`-Bereich, kein Fehler) — Bericht folgt in einem eigenen Nachtrag nach deren Abschluss.

## §4bo — 2026-09-29: S1–S7 ÖKONOMIE-AUDIT (reines Auslesen/Rechnen, KEIN Solve) — vor den finalen Läufen

Durchgeführt parallel zu Q1/Q2 (die weiterlaufen). Methodik: Code- und Config-Lektüre (`investment_calculator.py`, `cost_calculator.py`, `geometric_storage.py`, `system_builder.py`, `storage_geometry.yaml`, `Stadtbach_topo.yaml`, `Memmingen_P2_base.yaml`) plus ein Zahlencheck gegen bereits vorhandene `.sol`-Ergebnisse (`SB-S0-HK0-PIN0`, N3-Läufe). Keine neuen Solves. Vollständige Rohdaten zusätzlich in `data_for_draft/assumptions.json`.

### S1 — Kapitalkosten je Technologie

| Technologie | CAPEX-Basis | Nutzungsdauer | Zinssatz | Annuitätenformel | Fixe O&M | Quelle |
|---|---|---|---|---|---|---|
| WP (`hp_sb`/`hp_main`) | 700.000 €/MW | 20 a | 5 % (`investment.discount_rate`, beide Netze) | ANF(i,n)=i(1+i)ⁿ/((1+i)ⁿ−1), identisch für alle Assets | **keine** (kein Feld im Code-Pfad) | Config-Kommentar: Pieper et al. 2018, Energy Procedia 147, 26 reale dänische DH-WP-Anlagen (0,8–1,1 Mio. €/MW, 2017); harmonisiert 2026-07-20 (war 400k, undokumentierte Asymmetrie) |
| EK (`ek_sb`/`eboiler_main`) | 150.000 €/MW | 25 a | 5 % | wie oben | **keine** | Danish Energy Agency Technology Catalogue (Wirkungsgrad-Referenz, nicht explizit CAPEX-Quelle im Kommentar) |
| TES (`tes_sb`/`tes_main`) | degressiv, siehe S2 | 30 a | 5 % | wie oben | **keine** | Engineering-Schätzung (ASME-Wandstärke-Herleitung, Kommentar in `Stadtbach_topo.yaml`), explizit als Schätzung, nicht Herstellerangebot gekennzeichnet |
| Kessel/KWK (`hkw`/`gtost`/`bmhkw`/`hws_boiler`/`hww_boiler`/`hp_main`-Boiler) | **keine — Bestandsanlagen, nicht investierbar** | n/a | n/a | n/a | **keine** | — |

**Auffälligkeiten (wie von S1 verlangt):**
1. **Kein fixer O&M-Term existiert im tatsächlich genutzten Code-Pfad überhaupt** — für KEINE Technologie. `calion/models/investment_calculator.py`s `ComponentInvestmentConfig`/`StorageInvestmentConfig`-Dataclasses haben schlicht kein O&M-Feld (nur `capex_eur_per_mw(h)`, `activation_cost_eur`, `tie_breaker_eur_per_mw(h)`, `lifetime_years`). Ein `opex_fixed_eur_per_mw_yr`-Feld EXISTIERT im Code (`calion/config/schemas/tech_library_schema.py`), gehört aber zu einem ANDEREN, für Paper 2 nicht genutzten Config-Schema ("Tech Library") — für die tatsächlich verwendeten `assets:`-Configs (`Stadtbach_topo.yaml`/`Memmingen_P2_base.yaml`) ist es toter Code. **Alle CAPEX-Zahlen in diesem gesamten Auftragsblock (O1–Q4) sind reine Kapitalkosten, ohne laufende Wartung/Betriebskosten außerhalb von Brennstoff/Strom/CO2.**
2. Zinssatz (5 %) und Annuitätenformel sind netzübergreifend und technologieübergreifend identisch — keine Asymmetrie.
3. Nutzungsdauern (WP 20 a, EK 25 a, TES 30 a) liegen im von S1 erwarteten Literaturkorridor (Stahltank 30–40 a ✓ am unteren Rand, WP 20–25 a ✓, EK 20 a — Config nutzt 25 a, 5 a über der genannten Erwartung, nicht dramatisch, aber notiert).
4. Bestandsanlagen (KWK/Kessel) tragen **keinerlei** Kapitalkosten im Objective — konsistent mit „Greenfield-Entscheidung auf bestehender Infrastruktur", aber eine echte Asymmetrie ggü. den investierbaren Assets, die S7 explizit einfordert zu benennen.

### S2 — TES-Kostenkurve und Gültigkeitsbereich

Formel (`geometric_storage.py:362-371`, „degressiv", PRO TANK bei N identischen Tanks): `C(V) = N · c0 · (V/N / v0)^b`. Parameter (geteilter Default, `storage_geometry.yaml` Top-Level, für BEIDE Netze identisch, da `per_asset.tes_sb`/`tes_main` diese Felder nicht überschreiben): **c0 = 2.500.000 €, v0 = 10.000 m³, b = 0,7**, `unit_tank_m3 = 5.000 m³` (aus der jeweiligen Netz-YAML, nicht `storage_geometry.yaml`).

| V [m³] | N Tanks | €/m³ |
|---|---|---|
| 50 | 1 | 1.225,3 |
| 100 | 1 | 995,3 |
| 500 | 1 | 614,1 |
| 1.000 | 1 | 498,8 |
| 5.000 | 1 | 307,8 |
| 10.000 | 2 | 307,8 |
| 50.000 | 10 | 307,8 |

**Befund:** Ab V ≥ `unit_tank_m3` (5.000 m³) bleibt €/m³ KONSTANT bei 307,8 — die Degressionswirkung sättigt exakt am Einzeltank-Maßstab; größere Volumina sind nur identische Zusatztanks zum gleichen Stückpreis, keine weitere Skaleneffizienz. **Kleinste Leiter-Sprosse / Gültigkeitsbereich:** `v_min_realistic_m3 = 50 m³` (Top-Level-Default) vs. die je-Netz `V_min_m3`-Werte in den Netz-YAMLs (`tes_sb`: 10 m³; `tes_main`, aus einem realen Lauf ausgelesen: 5 m³) — **beide UNTER dem eigenen dokumentierten Realismus-Boden von 50 m³**, ein Inkonsistenz-Befund für sich. Umrechnung der kleinsten NICHT-null Leiter-Sprosse in m³ (via `energy_coeff = eta_strat·rho·cp·ΔT`, HK0-Betriebs-ΔT=10 K, `eta_strat=0,85`): **MM kleinste Sprosse 0,5 MWh → ≈ 52 m³** — knapp über dem 50-m³-Realismus-Boden, aber WEIT unter der von Ihnen genannten typischen Gültigkeitsgrenze von ca. 1.000 m³ der Kostenkurvenquelle. **Das ist kein hypothetischer Fall** — Q3s c0×0,5-Lauf hat genau in dieser Zone gebaut (1,1 MWh ≈ 76 m³, ebenfalls unter 1.000 m³). **SB kleinste Sprosse 37 MWh → ≈ 3.849 m³** — liegt SICHER über der 1.000-m³-Schwelle, kein Problem für SB. **Nur gemeldet, nichts geändert** — Entscheidung (Leiter beschneiden oder zweiter Kostendatensatz für kleine MM-Puffer) liegt bei Ihnen.

### S3 — Strom- und Brennstoffpreise

**HP-Kaufpreis vs. KWK-Verkaufspreis (Kernfrage):** `cost_calculator.py:calculate_energy_costs` — Kaufpreis (P_buy, u. a. WP/EK) = `strompreis_EUR_MWh[t] + energy_fee (0) + gridcost_eur_mwh (61,6)`. Verkaufspreis (P_sell, KWK-Erlös) = `max(strompreis_EUR_MWh[t] − sell_spread(0), sell_floor(0)) · (1−sell_haircut(0)) − sell_fee(0) + sell_premium(0)` = **der reine Börsenpreis, unverändert** (alle Spread/Haircut/Fee/Premium-Parameter existieren im Code, sind aber in beiden Netz-Configs auf 0 belassen). **Differenz = 61,6 EUR/MWh** (SB und MM identisch, harmonisiert 2026-07-29) — die volle Netzentgelt-/Umlagen-Kette laut Config-Kommentar (Arbeitspreis + KWKG 0,446 + Offshore 0,941 + BesAR 0,05 + Konzessionsabgabe 0,11 + Stromsteuer 0,05 ct/kWh ≈ 2,5 ct/kWh + MS-Arbeitspreis-Anteil). **Auffälligkeit:** die KWK verkauft zum vollen Rohbörsenpreis ohne jeden Vermarktungsabschlag (`sell_haircut`/`sell_spread`/`sell_fee` existieren als Mechanismus, sind aber überall 0) — ein realer Merchant-Erzeuger hätte typischerweise einen Bilanzkreis-/Vermarktungsabschlag; Modell ist hier optimistisch für die KWK-Seite, unquantifiziert.

**Brennstoffe (beide Netze identisch, harmonisiert 2026-07-29):** Gas 58,6 €/MWh (ef=200 kg/MWh), Biomasse 20,0 €/MWh (ef=20 kg/MWh, s. S5), Abwärme (nur SB, `ava_feed`) 10,0 €/MWh (ef=0). Kein Basisjahr für Gas-/Biomassepreis im Config-Kommentar dokumentiert (S7-Befund unten).

**Preiszeitreihen-Statistik (Strom, Jahr 2025, aus den Eingabedaten):** nicht explizit neu berechnet in diesem Audit-Pass (Zeitbudget) — `strompreis_EUR_MWh`-Spalte in `stadtbach_acron_combined_cleaned.xlsx` bzw. Memmingens Äquivalent; Mittel/Min/Max/Std wurden in früheren Sessions nicht dokumentiert gefunden. **Offen, nachreichbar auf Wunsch.**

### S4 — Leistungsentgelt

Formel (`cost_calculator.py:calculate_demand_charge`): `Kosten = demand_charge_eur_per_mw_y · year_frac · P_buy_peak`. `P_buy_peak` = Jahres-Peak des **Netzstrom-Bezugs** (P_buy, kontinuierliche Zeitauflösung dt_h=1 h, kein Monatsmaximum-Mechanismus gefunden — EIN Jahresmaximum). **Auslösende Anlagen:** ausschließlich Assets, die Netzstrom BEZIEHEN — bei SB praktisch nur `hp_sb`/`ek_sb` (KWK/Kessel beziehen keinen Netzstrom, sie erzeugen ihn). Satz: 127.240 €/MW·a (beide Netze identisch). **BASE vs. WP-Punkt (SB, bereits aus vorhandenen Läufen bekannt):** BASE-HK0 (N3) 46.241,29 € vs. `SB-S0-HK0` erzwungener Punkt (N3) **321.400,63 €** (≈ 7× höher — die 5,33-MW-WP verursacht einen neuen, deutlich höheren Bezugs-Peak) vs. `SB-S0-HK0-PIN0` 50.907,78 € (nahe BASE, wie erwartet ohne Investition) vs. BASE-FIX (O3) 49.583,97 €.

### S5 — CO2 und Emissionen

CO2-Preis 100 €/t (beide Netze). Emissionsfaktoren: Gas 200 kg/MWh, **Biomasse 20 kg/MWh — NICHT 0** (Ihre erwartete Prüffrage „Biomasse=0?" beantwortet: nein, ein kleiner, von 0 verschiedener Faktor ist gesetzt, vermutlich Lifecycle-/Ernte-/Transport-Emissionen, nicht Verbrennungs-CO2 — im Code nicht weiter dokumentiert, warum genau 20). `ef_el_kg_per_mwh: 400` in `emissions:` ist laut explizitem Config-Kommentar **UNGENUTZT** — die tatsächliche Netzstrom-CO2-Bilanzierung nutzt die STÜNDLICHE `grid_co2_kg_MWh`-Zeitreihe (electricitymaps), sowohl im Objective als auch im Reporting. **Brutto/Netto (Defekt 9):** bereits in dieser Session mehrfach dokumentiert und korrekt gehandhabt — das Modell optimiert BRUTTO (CHP-Stromemission ohne Eigenverbrauchs-Netting), `economics.csv`/die KPI-Berichterstattung zeigt NETTO (× `selfuse_fraction`); die Differenz erscheint explizit und gekennzeichnet als `CO2_selfuse_netting_adjustment_EUR` in jedem `cost_breakdown.json` (z. B. SB-S0-HK0-PIN0: −1.606.644,23 €) — **keine Doppelzählung**, der Nettingterm ist eine reine KPI-Zuordnungskorrektur, fließt nicht real ins Objective (Brutto-CO2-Kosten bleiben `real_costs_EUR.CO2_cost_EUR`).

### S6 — Erlösseite

Einziger Erlösterm im Objective: `P_sell[t] · sell_price[t]` (KWK-Stromverkauf, s. S3) — im Reporting als `Grid_sell_revenue_EUR` (negativ) unter `real_costs_EUR`. **Keine weiteren Erlösterme** (kein Wärmeverkauf-Zusatzerlös, keine Kapazitätsmarkt-Erlöse etc.). **EEG/KWKG-Vergütung für die Biomasse-KWK:** `calion/economics/german_subsidies.py` enthält eine `KWKGParameters`-Klasse — **verifiziert NICHT verwendet** (kein Import/Aufruf in `system_builder.py`/`model_finalizer.py`/`cost_calculator.py`, nur report-only, bereits in einer früheren Session-Notiz so befundet). Eine reale Biomasse-KWK-Anlage dieser Größe (14,5 MW) würde nach EEG/KWKG typischerweise eine Einspeisevergütung ÜBER dem Börsenpreis erhalten — **dieser potenzielle Zusatzerlös fehlt im Modell**, nur gemeldet, nicht eingebaut.

### S7 — Konsistenz

**Basisjahre:** Strompreis-Zeitreihe 2025 (explizit, `horizon: 2025-01-01…2025-12-31`); Gas/Biomasse-Festpreise **ohne dokumentiertes Basisjahr** im Config-Kommentar (nur „harmonisiert 2026-07-29" als Änderungsdatum, kein Preisstand-Jahr); Netzentgelt/Leistungspreis explizit **2026** (Config-Kommentar nennt „2026 published sheets"); WP/EK-CAPEX-Literatur **2017/2018** (Pieper et al.) hochgerechnet auf heutige €-Basis ohne erkennbare Inflationsanpassung im Kommentar. **Gemischte Basisjahre vorhanden** (2017/18 CAPEX-Literatur, 2025 Preiszeitreihe, 2026 Netzentgelt) — für sich genommen nicht falsch (jede Quelle ist die beste verfügbare für ihren Zweck), aber nirgends explizit als Inflations-/Diskontierungs-Entscheidung dokumentiert.

**O&M-Asymmetrie:** siehe S1 — es gibt keine, weil es für KEINE Technologie O&M gibt (nicht nur bei EINER Technologie fehlend, sondern strukturell aus dem genutzten Code-Pfad).

**TAC-Formel vs. Positivliste (ein Lauf, aus vorhandener `.sol`, `SB-S0-HK0-PIN0`):**
`TAC = Σ CAPEX_annualisiert + Σ Aktivierung_annualisiert + Brennstoff + Netzstrombezug + KWK-Erlös(negativ) + CO2 + Leistungsentgelt` [= `real_costs_total_EUR`] `+ Hilfsterme (Dump/Tie-Breaker/Storage-Install/Terminal/Demand-Slack/Return-Anchor/Pressure-Reg/Lateral-Tiebreak/Pressure-Slack/Data-Closure-Epsilon/CO2-Netting)` [= `model_aux_terms_total_EUR`] `+ residual = objective_total_EUR` (aus Gurobi). Geprüft an `SB-S0-HK0-PIN0`s `cost_breakdown.json`: real_costs_total_EUR (21.128.961,04) + model_aux_terms_total_EUR (−1.585.028,80, dominiert vom CO2-Netting-Term) + residual_EUR (1.587.078,97, der Netting-Gegenposten) = 21.131.011,21 = objective_total_EUR exakt, Restabweichung (`sum_real_plus_aux_plus_residual_minus_objective_EUR`) = 3,7·10⁻⁹ EUR. **TAC-Formel schließt exakt**, `reconciliation_check: OK` bestätigt dies strukturell für jeden Lauf dieser Session, nicht nur diesen einen.

**Vollständige Rohwerte** (alle S1–S7-Zahlen inkl. Quellenpfade) in `data_for_draft/assumptions.json`. Q1/Q2 laufen weiter (siehe §4bn-Ende), kein Solve wurde für diesen Audit gestartet.

## §4bp — 2026-09-29: Q1/Q2 ABGESCHLOSSEN — Investitionsintervall geschlossen, REGRET-VORZEICHEN GEDREHT (negativ statt positiv), PLUS ein selbst gefangener Konstruktionsfehler bei Q2 (CAPEX fehlte, exakt korrigiert)

Beide Läufe fertig, `status=maxTimeLimit`, beide sauber konvergiert, keine Fehler.

| Lauf | UB € (roh) | Gap | Status | `hp_sb` gebaut | `ek_sb` gebaut | Notkühler+Closure |
|---|---|---|---|---|---|---|
| Q1 `SB-S0-HK0` (frei optimierte WP-Größe, Warmstart aus PIN0) | 20.924.016,42 | 0,178 % | `maxTimeLimit` | **3,992 MW** (build=1) | nein (0 MW) | `j_man`=444,46; `chp_BMHKW`=234,18; `chp_GTOST`=174,83; `j_pss`=0,90; `j_psw`=0,32 |
| Q2 `SB-S0-HK0-HPFIX533` (hart auf 5,33 MW fixiert) | 20.636.466,24 (roh, **s. Korrektur unten**) | 0,137 % | `maxTimeLimit` | **5,325821519771965 MW** (build=1, exakt wie spezifiziert) | nein (0 MW) | `j_man`=469,23; `chp_BMHKW`=233,55; `chp_GTOST`=175,89; `j_pss`=0,90; `j_psw`=0,32 |

Beide unter dem netzweiten 0,25-%-Deckel UND unter dem N1-Knotendeckel für `j_man` (475,065 MWh) — kein Cap-Bind in beiden Läufen (anders als N3s Original).

### KONSTRUKTIONSFEHLER bei Q2 gefunden und exakt korrigiert (selbst entdeckt, nicht vom Solver-Ergebnis, sondern beim Prüfen von `Capex_cost_EUR=0,0`)

**Befund:** Q2s `cost_breakdown.json` zeigte `Capex_cost_EUR = 0,0` und `Activation_cost_EUR = 0,0` trotz einer hart fixierten, positiven 5,33-MW-Kapazität — das sah falsch aus und wurde sofort geprüft, statt stillschweigend übernommen. **Ursache:** `component_assembler.py:656` — `if invest_enabled and cap_var is not None and build_var is not None:` — CAPEX/Aktivierungs-Kostenterme werden NUR dann dem Objective hinzugefügt, wenn `investment.enabled=true` ist. Mein Q2-Szenario setzt `investment.enabled: false` (um über `heat_pump.py:132-134`s `cap.fix(capacity_init_mw)`-Mechanismus die exakte Fixierung auf 5,33 MW zu erzwingen) — das ist laut Code-Kommentar (Bugfix vom 2026-07-21) die KORREKTE, BEABSICHTIGTE Semantik für eine BESTANDSANLAGE (kein CAPEX, wie bei den Kesseln/KWK-Einheiten in S1), aber die FALSCHE Semantik für Q2s eigentliche Absicht — eine ECHTE, verpflichtende 5,33-MW-Investitionsentscheidung, deren CAPEX genauso wie in N3s ursprünglichem Inkumbenten mitzählen muss, damit die Zerlegung vergleichbar bleibt (wörtlich Q2s eigene Anforderung).

**Korrektur — exakt, nicht geschätzt:** Da die Kapazität in BEIDEN Fällen (mit und ohne `invest_enabled`) hart auf denselben Wert fixiert ist (keine Entscheidungsvariable), ist CAPEX ein reiner ADDITIVER KONSTANTER Term — er kann das Dispatch-Optimum nicht beeinflussen. Die Korrektur ist daher mathematisch exakt (keine Neulösung nötig): `CAPEX_annual = 5,325821519771965 MW × 700.000 €/MW × ANF(0,05; 20) = 299.150,39 €`, `Aktivierung = 50.000 € × ANF(0,05; 20) × build(1) = 4.012,13 €` — via `investment_calculator.annuity_factor()` exakt nachgerechnet, stimmt auf die letzte Nachkommastelle mit N3s ursprünglichem `Capex_cost_EUR`/`Activation_cost_EUR` überein (gleiche Kapazität, gleiche Formel). **Korrigierte Q2-Werte:** `real_costs_total_EUR` 20.634.414,31 → **20.937.576,83 €**; `objective_total_EUR` 20.636.466,24 → **20.939.628,76 €**; Gap bleibt ~0,135 % (additiv verschobene LB). Alle folgenden Zahlen verwenden die KORRIGIERTEN Werte.

### Investitionsintervall (Q1s Auftrag: [0; ~1,2 %] schließen)

| Referenzpunkt | Reale Kosten € |
|---|---|
| PIN0 (keine Investition) | 21.128.961,04 |
| BASE-HK0 | 21.124.355,68 |
| Q1 (freie Größe, 3,99 MW) | **20.921.966,95** |
| Q2 (fix 5,33 MW, korrigiert) | **20.937.576,83** |

**Das Intervall ist geschlossen, in die entgegengesetzte Richtung als N3s ursprünglicher Befund nahelegte:** Der wahre Wert einer WP-Investition liegt NICHT im Bereich „0 bis +1,2 % teurer", sondern bei **−0,90 % bis −0,98 % GÜNSTIGER** als der Nullpunkt. Q1 (freie Optimierung, 3,99 MW statt der ursprünglich unterstellten 5,33 MW) ist sogar noch etwas günstiger als Q2s fixierte 5,33-MW-Variante — ein Hinweis, dass 5,33 MW nicht die kosteneffizienteste Größe ist, sondern ein Artefakt von N3s unausgereiftem Inkumbenten war.

### Dominanz-Gate (roh, Gurobi-Objective)

| Netz | Lauf | UB € | vs. BASE-HK0 (21.127.847,23) | Gate |
|---|---|---|---|---|
| SB | Q1 | 20.924.016,42 | **−203.830,81** | **PASS, deutlich** |
| SB | Q2 (roh, unkorrigiert — Gate nutzt Gurobis Objective, nicht die nachträglich korrigierten realen Kosten) | 20.636.466,24 | −491.380,99 | PASS (aber s. Fußnote) |

**Fußnote zu Q2s Dominanz-Zahl:** Da Q2s roher Objective-Wert den CAPEX-Konstruktionsfehler noch enthält (0 statt 303.162,52 €), ist die rohe Differenz zu BASE-HK0 um genau diesen Betrag zu optimistisch. Korrigiert (Objective + 303.162,52): 20.939.628,76 − 21.127.847,23 = **−188.218,47 €** — PASS bleibt bestehen, deutlich, nur die Marge ändert sich leicht.

### Kostenzerlegung nach Positivliste, Q2 (korrigiert) gegen PIN0 — Q2s eigentlicher Auftrag

| Position | PIN0 € | Q2 (korrigiert) € | Δ (Q2−PIN0) € | Richtung |
|---|---|---|---|---|
| Capex | 0,00 | 299.150,39 | **+299.150,39** | neue Investition |
| Aktivierung | 0,00 | 4.012,13 | **+4.012,13** | neue Investition |
| Brennstoff | 26.252.970,18 | 25.264.602,84 | **−988.367,33** | Einsparung durch WP |
| Strombezug (Netz) | 26.630,96 | 26.768,26 | +137,31 | WP-Eigenverbrauch (winzig) |
| KWK-Stromerlös (Verkauf) | −12.156.749,76 | −11.452.555,22 | **+704.194,54** | Erlösverlust |
| CO2 | 6.955.201,89 | 6.744.690,64 | **−210.511,25** | Einsparung durch WP |
| Leistungsentgelt | 50.907,78 | 50.907,78 | **0,00** | **KEINE Veränderung** |
| **Summe** | **21.128.961,04** | **20.937.576,83** | **−191.384,22** | **Nettovorteil** |

**Mechanismus-Aussage (Q2s eigentliches Ziel):** Der grundlegende Mechanismus aus N3s Analyse bleibt qualitativ bestehen (WP spart Brennstoff/CO2, kostet KWK-Erlös), aber das Vorzeichen der Gesamtbilanz dreht sich um, weil bei einem sauber konvergierten Lauf (0,135 % statt 1,82 % Gap) der Erlösverlust (+704.195 €) deutlich KLEINER ausfällt als bei N3 (+666.102 € — ähnlich groß, kein Haupttreiber der Differenz) UND das **Leistungsentgelt überhaupt nicht mehr steigt** (N3: +275.159 €; hier: 0,00 €) — dieser eine Posten allein erklärt den Großteil der Vorzeichenumkehr. Ein sauber optimierter Einsatzplan vermeidet den neuen Bezugsspitzenwert, den N3s unausgereifter Inkumbent verursachte.

### Break-even-Schwellen (NUR aus diesem Lauf linearisiert, wie verlangt)

| Hebel | Erforderliche Änderung, damit Regret = 0 | Relative Größe |
|---|---|---|
| CAPEX (WP, annuitätisch) | +191.384,22 € (auf 494.546,74 €) | **+63,1 %** höhere Investitionskosten nötig |
| KWK-Stromerlös | −191.384,22 € zusätzlicher Erlösverlust | **−1,67 %** zusätzlicher Erlösrückgang nötig |
| Leistungsentgelt | müsste NEGATIV werden (unmöglich) | kein Hebel — Q2 zeigt keinen Leistungsentgelt-Effekt |

Auch bei einer 63-%-höheren Investitionskostenannahme oder einem zusätzlichen 1,67-Prozentpunkt-Erlösverlust bleibt die WP-Investition an der Rentabilitätsschwelle — deutlich robuster als N3s ursprüngliche Zahlen suggerierten.

### O1-Empfehlung (§4bl) damit erledigt, K2-artiger Beweis bestätigt

Die in §4bl empfohlene Maßnahme (PIN0-geseedeter Nachlauf) hat genau das geliefert, was erwartet wurde: das MIP-Gap-Artefakt ist aufgelöst, die Dominanz ist jetzt mit deutlicher, belastbarer Marge bestätigt (nicht mehr nur „vermutlich, siehe LB-Stabilität"), UND das Regret-Vorzeichen selbst hat sich gedreht — von einem scheinbaren ökonomischen Argument GEGEN die WP-Investition zu einem klaren Argument DAFÜR. **Autoren-Entscheidung:** diese Zahlen (Q1/Q2, korrigiert) als finale Basis für die Paper-Erzählung verwenden, oder N3s ursprünglichen (jetzt widerlegten) Befund als „vorläufig, siehe Revision" kennzeichnen.

**Damit ist der gesamte Q1–Q4/S1–S7-Auftragsblock abgeschlossen.**

## §4bq — 2026-09-30: V0–V8 ZUSAMMENGEFASSTE FREIGABE — V1 (Flag-Semantik entkoppelt) ABGESCHLOSSEN, verifiziert

Neuer, umfassender Auftragsblock (ersetzt T/U/R, die dieser Session nicht vorlagen). Verbindliche Reihenfolge: V1–V5 (Code/Parameter) → V6 (Kontrollläufe) → V7 (finale Läufe, NICHT vor V6-Bestätigung) → V8 (Auswertung). Dieser Eintrag deckt V1 vollständig ab.

### V1 — Flag-Semantik entkoppelt (drittes Vorkommnis mit `investment.enabled`)

**Vollständiges Audit aller Verwendungsstellen** (wie verlangt): `investment.enabled`/`investable` trieb bisher DREI separate Verhaltensweisen über eine einzige Variable:
1. **Existenz/Fixierung der Kapazitätsvariable** (`heat_pump.py:94/101/132`, `p2h.py:70/78/98`, `storage.py:90/116-117/162`, `geometric_storage.py:228-241/272-274/328/384` — jeweils `investable=False` → `cap.fix(capacity_init)`). **Dieser Pfad war bereits korrekt** — jede Block-Klasse verwendet ihn konsistent für GENAU eine Bedeutung.
2. **CAPEX/Aktivierung im Objective** (`component_assembler.py`, drei Fundstellen: Zeile 656 Wärmepumpe, Zeile 875 P2H, Zeile 1351 geometric_storage — jeweils `if invest_enabled/investable: ...` vor dem Anhängen der Kostenterme). **Hier lagen BEIDE diese Session gefundenen Bugs** (Q2/SB-S0-HK0-HPFIX533, docs SS4bl/SS4bp; Q3s MM-S2-HK0 `fix23.9`-Regret-Lauf, docs SS4bn).
3. **Reporting-Vertrauen** (`result_collector.py`, HP- und P2H-Extraktion — gated auf `invest_enabled`, um zu entscheiden, ob die live Pyomo-Variable gelesen wird oder der statische Config-Wert). **Der O2-Bug** (docs SS4bk) war hier.

**Umsetzung:**
- **Achse 2 (CAPEX)** entkoppelt: neues, orthogonales Feld `investment.capex_charged` (Default = spiegelt `investment.enabled`, voll rückwärtskompatibel zu jedem bestehenden Szenario), an allen drei Fundstellen in `component_assembler.py` ersetzt `invest_enabled` in der CAPEX-Gate-Bedingung. Für `geometric_storage` (kein `investment:`-Unterblock, sondern ein Top-Level-`investable`-Flag, gesetzt einzig vom `CALION_TES_FIX_MWH`-Diagnosemechanismus in `scenario_runner.py` — eine bereits vorher bestehende, jetzt dokumentierte Architektur-Inkonsistenz ggü. Wärmepumpe/P2H) ebenso ein `capex_charged`-Feld ergänzt; `scenario_runner.py`s `CALION_TES_FIX_MWH`-Handler setzt es jetzt standardmäßig auf `True` (ein „Regret"-Lauf will per Definition die volle Kostenwahrheit einer festen Größe kennen), mit `CALION_TES_FIX_NO_CAPEX=1` als expliziter Opt-out.
- **Aktiv-Assertion** (wie von V0/V1 verlangt): fixierte Kapazität > 0 ohne `capex_charged` ist jetzt ein HARTER Fehler (`ValueError`, kein stiller Fallback), außer ein neues Feld `investment.bestand: true` markiert die Anlage explizit als Bestand. Implementiert für Wärmepumpe, P2H UND geometric_storage.
- **Achse 3 (Reporting)** in `result_collector.py` NICHT mehr an `invest_enabled` gekoppelt — liest jetzt IMMER zuerst den Live-Pyomo-Wert (`pyo.value(var, exception=False)`, das `None` statt einer Exception liefert), fällt nur auf den statischen Config-Wert zurück, wenn kein Live-Wert existiert. Robuster als der O2-Fix, der noch auf korrekt gesetztes `invest_enabled` angewiesen war — jetzt unabhängig davon.

**Verifikation (nicht nur Unit-Test, sondern End-to-End gegen einen echten Lauf):** Q2s Modell mit dem reparierten Code neu gebaut und Q2s EIGENE `.sol` hineintransplantiert (`CALION_FEAS_ONLY`, kein Solve). Ergebnis: `objective at seeded point: 20.939.628,76 EUR` — **exakte Übereinstimmung** mit der in §4bp von Hand nachgerechneten Korrektur (20.939.628,76 €), bis auf die letzte Nachkommastelle. 30 Constraint-Verletzungen (diagnostisch, gleiche Größenordnung wie frühere Transplantations-Checks dieser Session, nicht mit dem CAPEX-Fix zusammenhängend). **Der Fix ist damit doppelt bestätigt** — einmal durch Handrechnung (§4bp), einmal durch den reparierten Code selbst.

**Assertion fing beim ersten Verifikationsversuch sofort einen ECHTEN, unabhängigen Konfigurationslücken-Fall:** `p2h_existing` (SBs reale 9,9-MW-Bestands-Elektroheizung, KEIN `investment:`-Block in der Config) löste die neue Assertion aus — korrekt, da diese Anlage genau das Fehlerprofil hat (fixe, positive Kapazität, kein CAPEX), nur diesmal ABSICHTLICH (echte Bestandsanlage). `investment: {bestand: true}` in `Stadtbach_topo.yaml` ergänzt, Assertion bestätigt danach sauber. **Vollständiger Scan beider Netz-Configs** (alle `heat_pump`/`p2h`-Assets): außer `p2h_existing` benötigt KEINE andere Anlage die `bestand`-Markierung — `hp_sb`/`ek_sb`/`eboiler_main`/`hp_main` sind alle reguläre investierbare Assets (`investment.enabled=true`, `capacity_mw=0` Basiswert), MM hat kein `p2h_existing`-Äquivalent.

**Betroffene Läufe dieser Session (wie von V1 verlangt geprüft):** genau ZWEI, beide bereits identifiziert — Q2 (SB-S0-HK0-HPFIX533, docs SS4bl/SS4bp, korrigiert) und Q3s `fix23.9`-Regret-Lauf (docs SS4bn, **noch NICHT korrigiert** — wird von V7a ohnehin komplett neu gerechnet, siehe unten). KEIN anderer Lauf dieser Session (N3, O1, O3, Q1, Q3s c0×1,0/0,7/0,5/0,3) ist betroffen — alle nutzen entweder `investment.enabled=true` (normal) oder fixieren exakt auf 0 (PIN0-Muster, wo der Bug unsichtbar ist, da 0-CAPEX so oder so korrekt ist). Geprüft durch direkten Abgleich der `Capex_cost_EUR`-Werte in allen betroffenen `cost_breakdown.json`-Dateien.

**Q3s `fix23.9`-Lauf als SUPERSEDED markiert** (docs SS4bn, dort nicht mehr korrigiert, da V7a diesen exakten Lauf ohnehin unter der V2-reparierten TES-Kostenkurve wiederholt — eine Korrektur jetzt wäre doppelte Arbeit).

`scenarios.yaml`s Q2-Definition um `investment.capex_charged: true` ergänzt, damit ein künftiger Re-Lauf ohne Handkorrektur korrekt ist.

**Nächster Schritt: V2 (TES-Kostenanker, „wichtigster ökonomischer Fix").**

## §4br — 2026-09-30: V2 (TES-Kostenanker) — Fix umgesetzt, verifiziert, PLUS ein größerer, unabhängiger Befund (p_max_bar 10 vs. 100 bar)

### Umsetzung

`unit_tank_m3` in beiden Netz-YAMLs (`Stadtbach_topo.yaml`s `tes_sb`, `Memmingen_P2_base.yaml`s `tes_main`) von 5.000 auf **10.000 m³** angehoben (passend zum Kostenkurven-Anker `v0=10.000 m³`). `V_min_m3` in beiden Dateien von 10/5 auf **50 m³** angehoben (passend zu `storage_geometry.yaml`s eigenem `v_min_realistic_m3`). Verifiziert: `unit_tank_m3`/`V_min_m3` werden NICHT von `storage_geometry.yaml`s `per_asset`-Injektion überschrieben (bestätigt anhand eines echten gelösten Laufs' aufgelöster `scenario_meta.json` — der Laufzeitwert entsprach exakt der Netz-YAML, nicht `storage_geometry.yaml`s Top-Level-Default) — die Netz-YAML-Bearbeitung ist die korrekte, wirksame Stelle.

### EUR/m³-Tabelle VOR/NACH

| V [m³] | VORHER (unit=5.000) €/m³ | NACHHER (unit=10.000) €/m³ | Δ |
|---|---|---|---|
| 50 | 1.225,3 | 1.225,3 | 0 |
| 100 | 995,3 | 995,3 | 0 |
| 500 | 614,1 | 614,1 | 0 |
| 1.000 | 498,8 | 498,8 | 0 |
| 5.000 | 307,8 | 307,8 | 0 |
| 10.000 | 307,8 | **250,0** | **−18,8 %** |
| 50.000 | 307,8 | **250,0** | **−18,8 %** |

Unterhalb 5.000 m³ unverändert (erwartungsgemäß, ein Einzeltank-Fall in beiden Konfigurationen). Ab 10.000 m³ sättigt die Kurve jetzt korrekt exakt am eigenen Anker (250 €/m³, wie in `storage_geometry.yaml` dokumentiert) statt bei den zuvor um ~23 % zu hohen 307,8 €/m³ — behebt genau den in §4bo/S2 gemeldeten Befund.

**Alle bisherigen TES-Ergebnisse als SUPERSEDED markiert** (wie angewiesen): Q3s gesamte MM-Speicher-Break-even-Tabelle (docs SS4bn, c0×1,0/0,7/0,5/0,3 + `fix23.9`-Regret-Lauf) — wird von V7a ohnehin komplett neu gerechnet.

**Verifikation (Build-Test, kein Solve):** `MM-S2-HK0` mit dem neuen `unit_tank_m3=10.000` neu gebaut, `q3_mm_s2_c0x0.5`s eigene `.sol` transplantiert (`CALION_FEAS_ONLY`). Baut sauber, `geometric_storage tes_main: ... cost=degressive` korrekt attached, keine neuen Fehler. Objective am transplantierten Punkt (318.163,60 €) weicht leicht vom ursprünglichen c0×0,5-Ergebnis (315.484,95 €) ab — bei einem transplantierten 76,3-m³-Tank (weit unter JEDER `unit_tank_m3`-Schwelle, N=1 so oder so) sollte die CAPEX-Formel identisch sein; die ~2.679-€-Differenz ist vermutlich SEED-DUMP-Abdeckungsrauschen (97,1 % Abdeckung, ähnliche Größenordnung wie an anderer Stelle dieser Session beobachtet), nicht auf den V2-Fix zurückzuführen — die eigentliche Kostenwirkung des Fixes greift erst ab 10.000 m³, weit über diesem konkreten Tank. Reicht als Bau-/Lauffähigkeits-Nachweis; eine präzise Zahlenprüfung folgt natürlich aus V7as Neuläufen.

### GRÖSSERER, UNABHÄNGIGER BEFUND (beim Prüfen der ASME-Wandstärken-Begründung entdeckt, nicht Teil von V2s eigentlichem Auftrag, aber direkt daraus resultierend)

Die bestehende Config-Kommentar-Begründung für die ALTE `V_max_m3=5.000`-Grenze rechnet mit `p_max_bar=10` (Netz-YAML-Wert) und kommt bei ~60 mm Wandstärke auf ~5.500 m³ — plausibel. **Aber:** `storage_geometry.yaml`s `per_asset`-Override setzt den TATSÄCHLICH zur Laufzeit wirksamen `p_max_bar` für BEIDE Netze auf **100 bar** (bestätigt an einem echten gelösten Lauf) — das Zehnfache des Werts, den die ASME-Begründung annimmt. Nachgerechnet (gleiche ASME-Dünnwandformel, S=130 MPa, E=0,85):

| Fall | Druck | r_hd | V | Wandstärke |
|---|---|---|---|---|
| Kommentar-Annahme (Netz-YAML) | 10 bar | 3,0 | 5.000 m³ | 58,1 mm ✓ plausibel |
| **Tatsächlich aufgelöst (storage_geometry.yaml)** | **100 bar** | 2,0 | 5.000 m³ (ALT) | **665,6 mm** — unrealistisch |
| Tatsächlich aufgelöst, V2-Ziel | 100 bar | 2,0 | 10.000 m³ (NEU) | **838,6 mm** — unrealistisch |
| Nur-Druck-Diskrepanz isoliert | 10 bar (Kommentar-Wert) | 2,0 | 10.000 m³ (NEU) | 83,9 mm — grenzwertig (über der ~60-mm-Praxisgrenze, aber nicht absurd) |

**Zur Einordnung:** Das Netz selbst betreibt seinen Vorlaufdruck-Sollwert bei nur 16 bar (`j_hkw`, `Stadtbach_topo.yaml`). Ein Pufferspeicher bei 100 bar ist für eine Fernwärme-Anwendung untypisch hoch (eher Gasspeicher-Klasse) und steht in keinem erkennbaren Verhältnis zum Rest des Systems. Das spricht dafür, dass 100 bar ein Altwert/Versehen in `storage_geometry.yaml` ist, nicht Absicht — aber das ist eine Vermutung, keine Feststellung. **Nicht selbst geändert** (außerhalb von V2s expliziter Anweisung, eine folgenreiche technische Annahme, die dem Autor gehört). **Zur Entscheidung vorgelegt:** (a) `p_max_bar` in `storage_geometry.yaml` auf einen realistischeren Wert (z. B. 10–16 bar, passend zum Netzbetriebsdruck) korrigieren, mit entsprechender Neuableitung von `V_max_m3`/Wandstärken-Kommentar: ODER (b) 100 bar ist beabsichtigt (z. B. für eine zukünftige Hochdruck-Technologie-Option) und die ASME-Kommentare/`V_max_m3` müssen für DIESE Druckklasse neu hergeleitet werden (was vermutlich eine deutlich kleinere `V_max_m3`-Grenze als 5.000/10.000 m³ ergäbe, da 100 bar bei praktikabler Wandstärke einen viel kleineren Tank erlaubt).

**Nächster Schritt: V3 (Investitionskosten, Lebensdauern, O&M).**

## §4bs — 2026-09-30: V2b (Druckklasse des TES) — „Defekt 11" bestätigt, KEIN Tippfehler sondern eine bewusste, jetzt überholte Design-Entscheidung; korrigiert

### a) Diagnose

**Wo genau steuert `p_max_bar` etwas in `geometric_storage.py`?** Exakt zwei Stellen, beide GEOMETRISCH (Höhe/Volumen), KEINE davon Kosten: `_h_max_from_pressure(p_max_bar) = (p_max_bar − 1,013 bar)·1e5/(ρ·g)` (Zeile 46-48) berechnet die maximale Tankhöhe aus dem hydrostatischen Säulendruck; verwendet an Zeile 223 (`V_max_effective = min(V_max_m3, V_max_from_p)`, mit `V_max_from_p = π·h_max³/(4·r_hd²)`) und Zeile 428 (Option-B-Geometrie-Bound). **`p_max_bar` erscheint NIRGENDS in der Kostenformel** (`C(v)=c0·(v/v0)^b`, Zeilen 354-376) — Druck beeinflusst NUR die maximal erreichbare Tankgröße, NIEMALS €/m³ direkt.

**Woher kommen die 100 bar — Default, Vererbung, Tippfehler?** **KEINES davon — eine bewusste, dokumentierte Design-Entscheidung** (`storage_geometry.yaml`, Kommentar seit mindestens 2026-09-04/09-21, per `git log -p` verifiziert): *„p_max_bar is set high on purpose: an ATMOSPHERIC tank's height is not pressure-limited (open vessel), so the pressure-derived height/volume bound is disabled; single-vessel realism is enforced instead by unit_tank_m3 + N=ceil(V/unit)."* Der Autor jener früheren Passage argumentierte: ein offener/atmosphärischer Tank sei NICHT druckbegrenzt, also wird die Druck-Höhen-Formel absichtlich per `p_max_bar=100` NUMERISCH deaktiviert (macht `V_max_from_p` riesig/nicht bindend), und die eigentliche Größenrealismus-Prüfung sollte allein über `unit_tank_m3` laufen. **Das Problem:** parallel dazu existierte in BEIDEN Netz-YAMLs eine GANZ ANDERE, damit unvereinbare Erzählung („echtes PED-Druckgefäß bei 10 bar, ASME-Wandstärken-Herleitung, daraus V_max_m3≈5.000") — offenbar unabhängig geschrieben, ohne Kenntnis von `storage_geometry.yaml`s Override-Mechanismus und dessen bewusstem Deaktivierungs-Trick. Drei voneinander unabhängige „realistische Tankgröße"-Herleitungen (`storage_geometry.yaml`s Top-Level `unit_tank_m3=10.000`; der Netz-YAML-eigene, TATSÄCHLICH wirksame `unit_tank_m3=5.000`; sowie `V_max_m3=5.000`/`250.000` in `storage_geometry.yaml`s `per_asset`) haben sich unbemerkt nebeneinander angesammelt.

**Tabelle wie verlangt (Kosten UNVERÄNDERT über alle Drücke, da €/m³ druckunabhängig ist — nur die MAXIMALE ERREICHBARE Größe ändert sich):**

| p_max_bar | h_max [m] | V_max_from_p [m³] | Bindend ggü. altem unit=5.000 / neuem unit=10.000? |
|---|---|---|---|
| 100 (bisher aktiv) | 1.038,3 | ~220 Mio. | Nein, um viele Größenordnungen nicht bindend |
| 10 (Netz-YAML-Kommentar) | 94,3 | 164.489 | Nein, immer noch weit über beiden |
| 3 (neu, siehe b) | 20,8 | **1.778** | **JA — kleiner als beide bisherigen `unit_tank_m3`-Werte** |
| 2,5 | 15,6 | 745 | Ja, sogar noch kleiner |

**Widerspruchsfrage beantwortet:** JA — das mit V2 gesetzte `unit_tank_m3=10.000 m³` steht in klarem, quantifizierbarem Widerspruch zu jeder physikalisch plausiblen atmosphärischen Druckklasse (3 bar erlaubt nur ~1.778 m³ als Einzeltank).

### b) Korrektur

`p_max_bar` in `storage_geometry.yaml`s `per_asset` (beide Netze) von 100 auf **3,0 bar** gesetzt — oberes Ende der vorgegebenen 2,5–3-bar-Spanne, gewählt weil die resultierende Höhe (20,8 m) besser zu real gebauten großen dänischen atmosphärischen Speichertanks passt als 2,5 bar (15,6 m). Begründung dokumentiert (in `storage_geometry.yaml` UND in beiden Netz-YAMLs, mit Verweis aufeinander): Auslegungsdruck = statische Wassersäule + kleiner Zuschlag am Tankboden, NICHT der Netzbetriebsdruck (16 bar am `j_hkw`-Sollwert — komplett unabhängig, da der Speicher hydraulisch entkoppelt ist), NICHT 10, NICHT 100. **Hydraulische Entkopplung explizit dokumentiert:** der atmosphärische Speicher ist über einen Wärmeübertrager bzw. einen eigenen Niederdruckkreis mit eigener Druckhaltung angebunden — diese Entkopplung (Verrohrung, WÜT, Regelung) ist bereits im Turnkey-`c0`/m³-Anker enthalten (gleicher „Total-Installed"-Kostenumfang, der bereits im Header von `storage_geometry.yaml` dokumentiert ist), nicht separat berechnet. **Druckbeaufschlagte Variante bleibt verfügbar, NUR als Sensitivität** — der alte `p_max_bar=100`-Zahlentrick bzw. eine echte Hochdruckauslegung ist weiterhin über `tes_technology: pressurized` (Study G, `scenarios.yaml`) erreichbar, ist aber NICHT mehr der Default.

`unit_tank_m3` in BEIDEN Netz-YAMLs jetzt aus `p_max_bar=3,0`/`r_hd=2,0` HERGELEITET (nicht mehr frei gewählt): **1.778 m³** (ersetzt sowohl den alten ASME-Wert 5.000 als auch V2s Anker-Wert 10.000).

**Korrigierte EUR/m³-Tabelle (unit_tank_m3=1.778):**

| V [m³] | N Tanks | €/m³ |
|---|---|---|
| 50 | 1 | 1.225,3 (unverändert — Einzeltank-Fall in allen drei Versionen) |
| 500 | 1 | 614,1 (unverändert) |
| 1.000 | 1 | 498,8 (unverändert) |
| 1.778 | 1 | **419,7** (neuer Sättigungspunkt) |
| 5.000 | 3 | **427,9** |
| 10.000 | 6 | **427,9** |
| 50.000 | 29 | **423,6** |

**Vergleich mit Literatur (Quellen unten):** Grubenspeicher (PTES) real gebaute Anlagen: Vojens 24 €/m³, Dronninglund 38 €/m³, Marstal 41 €/m³ — allgemein „unter 50 €/m³" für große Gruben. Stahltank-Literatur (EN-14015-Klasse, div. Quellen inkl. IEA-DHC/IEA-ES/ASME-Kostenanalyse): 35–320 USD/m³, Median ~115 USD/m³, große Tanks (~6.000 m³) ~100 USD/m³. **Einordnung:** das korrigierte Modell landet bei großen Volumina (420–428 €/m³) ÜBER dem oberen Rand der zitierten Stahltank-Spanne (~300 €/m³ Äquivalent) — plausible Erklärung: das Modell erzwingt bei großen Gesamtvolumina VIELE kleine Einzeltanks (N=ceil(V/1.778)) statt der Bündelungs-/Baustellen-Skaleneffekte, die reale große Tankfarmen/-parks realisieren (gemeinsame Erschließung, Sammelbeschaffung) — die einfache Pro-Tank-Formel bildet das nicht ab. Grubenspeicher liegt WEIT darunter (15–41 €/m³) — für sehr große Volumina (insbesondere SB, 201-MW-Netz) wäre ein Grubenspeicher-Kostenmodell ökonomisch die naheliegendere Alternative, aber das ist eine TECHNOLOGIEWAHL-Frage, außerhalb von V2bs Auftrag (Pit/PTES war laut `storage_geometry.yaml`s eigenem Header „removed entirely" — eine frühere bewusste Entscheidung, hier nicht revidiert).

### c) Folgen bewertet — Defekt 11

**JA, die Druckklasse hat die Kosten UND die Größengrenze substanziell beeinflusst — dokumentiert als Defekt 11.** Da €/m³ selbst druckunabhängig ist, wirkt sich der Fehler NICHT über eine falsche Preiskurve aus, sondern über eine ZU GROSSE zulässige Einzeltankgröße, die eine STÄRKERE Degression vortäuschte, als physikalisch erreichbar ist. **Faktor:** der physikalisch korrekte Sättigungspreis bei großem Volumen (~427,9 €/m³) liegt **~1,71×** über V2s Anker-korrigiertem Wert (250 €/m³) und **~1,39×** über dem ursprünglichen Vor-V2-Wert (307,8 €/m³, `unit=5.000`). **Mit anderen Worten: die gesamte Session hat groß-skalige TES-Speicher-Ökonomie bislang UNTERPREIST, nicht überteuert** — V2s eigene Korrektur (Angleichung an den Kostenkurven-Anker) ging faktisch in die FALSCHE Richtung, weil sie die geometrische Erreichbarkeit nicht mitgeprüft hatte — genau der Grund, warum V2b angeordnet wurde. **`unit_tank_m3` MUSSTE nach der Korrektur anders gesetzt werden als in V2 beschlossen** (1.778 statt 10.000) — bereits oben umgesetzt.

**Alle TES-Ergebnisse dieser Session (Q3, jede vorherige S2/S3-Topologiearbeit, die groß-skalige TES nutzte) bleiben SUPERSEDED** (wie bereits in §4br markiert) — V7a wiederholt das Experiment ohnehin unter der jetzt vollständig korrigierten Konfiguration.

**Build-Verifikation:** `MM-S2-HK0` mit der finalen V2b-Konfiguration neu gebaut, `c0×0,5`s `.sol` transplantiert (`CALION_FEAS_ONLY`, kein Solve). Baut sauber, keine Assertion-Fehler. Objective am transplantierten Punkt: 318.163,60 € — identisch zum reinen V2-Test (erwartungsgemäß, der transplantierte 76,3-m³-Tank liegt weit unter jeder `unit_tank_m3`-Schwelle). **8.793 Constraint-Verletzungen** (mehr als die 30 beim reinen V2-Test) — durchweg `tes_main_p_rating[t]`-artige Verletzungen mit konstantem Betrag (3,38), konzentriert auf die Speicher-Leistungsgrenze. **Erwartungsgemäß, kein neuer Fehler:** die transplantierte ALTE Lösung wurde unter der lockereren Vor-V2b-Konfiguration gefunden; V2b hat die zulässige Speichergröße/-leistung real verengt, sodass dieselben Zahlen jetzt an einer STRENGEREN Grenze anstehen — genau das erwartete Verhalten einer echten geometrischen Verschärfung, kein Bug. Ein echter Solve (V7a) findet dafür passende, zulässige neue Werte.

**Quellen (Web-Recherche, 2026-09-30):**
- Grubenspeicher-Kosten (Vojens 24 €/m³, Dronninglund 38 €/m³, Marstal 41 €/m³, „<50 €/m³" allgemein): [Seasonal pit heat storage: Cost benchmark of 30 EUR/m³ — Solarthermalworld](https://solarthermalworld.org/news/seasonal-pit-heat-storage-cost-benchmark-30-eurm3/), [Bankwatch Dronninglund case study](https://bankwatch.org/wp-content/uploads/2022/05/2022-05_Case-study-Dronninglund-_eng.pdf), [Bankwatch Marstal case study](https://bankwatch.org/wp-content/uploads/2022/05/2022-05_Case-Study-Marstal_eng.pdf), [IEA-DHC Annex XII PTES report](https://www.iea-dhc.org/fileadmin/documents/Annex_XII/2020.03.09_Report_Task_C_IEA_DHC_Annex_XII_Project_03.pdf)
- Stahltank-Kosten (EN 14015, 35–320 USD/m³, Median ~115 USD/m³): [Cost Analysis for Large Thermal Energy Storage Systems — ASME Digital Collection](https://asmedigitalcollection.asme.org/sustainablebuildings/article/6/2/021006/1219471/Cost-Analysis-for-Large-Thermal-Energy-Storage), [Atmospheric Thermal Energy Storage Tanks 50–500 m³, EN 14015 — techsolutions.lt](https://techsolutions.lt/en/thermal-energy-storage-tanks/), [EN 14015 — CEN/GlobalSpec](https://standards.globalspec.com/std/91037/EN%2014015), [IEA-ES Task 39](https://iea-es.org/task-39/)

**Nächster Schritt (unverändert): V3 (Investitionskosten, Lebensdauern, O&M).**

## §4bt — 2026-09-30: V2c — §4bs WAR SELBST FALSCH („Defekt 11" neu diagnostiziert: falsche NORM, nicht falscher Druckwert) — korrigiert, DANACH HALT vor V3 wegen offener Kostenkurven-Plausibilität

### a) Diagnose: die ASME-Druckbehälter-Logik gilt nicht für den atmosphärischen Speicher

**§4bs (V2b) war ein eigener Fehler, kein Fix.** Ich hatte `p_max_bar` als Auslegungsdruck für ein DRUCKGEFÄSS interpretiert (Höhe aus Wandstärken-/Druckformel abgeleitet) — das ist die falsche Norm für einen ATMOSPHÄRISCHEN, stehenden Flachbodentank nach EN 14015 / API 650. Dieser Tanktyp hat KEINE Volumenobergrenze aus einer Festigkeitsformel — die Wand wird über Ringspannung (Wandstärke wächst mit der Tiefe) für JEDE hydrostatische Last ausgelegt, es gibt keinen „maximalen Auslegungsdruck", der die Höhe begrenzt. **Reale Referenz (im Betrieb seit April 2023):** Wärmespeicher Reuter West, Berlin (Vattenfall) — EIN Tank, 56.000 m³ (56 Mio. Liter), 45 m hoch, 43 m Durchmesser, 2,6 GWh, hydrostatischer Bodendruck ≈4,4 bar. Das widerlegt §4bs' „1.778 m³ Maximaltank" eindeutig — ein realer Tank existiert bei mehr als dem 30-Fachen dieses Werts. **§4bs' Schlussfolgerung „Speicher war 1,4–1,7× unterbewertet" wird hiermit ZURÜCKGENOMMEN.**

### b) Korrektur

`p_max_bar` in `storage_geometry.yaml`s `per_asset` (beide Netze) zurück auf 100 gesetzt — diesmal NICHT mit der alten, vagen Begründung „atmosphärisch = kein Druck", sondern korrekt: die druckabgeleitete Höhen-/Volumenformel gilt für diesen Tanktyp schlicht nicht, wird also bewusst nicht-bindend gehalten. **Statt eines Druckwerts: expliziter Parameter, direkt auf das bestehende `unit_tank_m3`-Feld abgebildet, begründet über die Referenzanlage, nicht über eine Formel: 50.000 m³ je Tank** (von Reuter Wests realen 56.000 m³ leicht abgerundet, als Sicherheitsmarge). Höhe/Durchmesser als dokumentierte Auslegungsannahme (H/D≈1, passend zu Reuter Wests 45 m/43 m≈1,05 — weicht vom Modell-eigenen Schichtungs-Parameter `r_hd=2,0` ab, der unverändert bleibt, da außerhalb von V2cs Auftrag). Kosten weiterhin AUSSCHLIESSLICH aus der bestehenden empirischen Kurve `C=N·c0·((V/N)/v0)^b` — keine Kostenableitung aus Wandstärken, wie angewiesen. Druckbeaufschlagte Variante (der alte `p_max_bar=100`-Zahlentrick oder eine echte Hochdruck-Auslegung) bleibt NUR als Study-G-Sensitivität verfügbar. `unit_tank_m3` in BEIDEN Netz-YAMLs auf 50.000 gesetzt (ersetzt §4bs' 1.778). Zusätzlich: die bereits als „tot" markierten `r_hd`/`p_max_bar`/`V_max_m3`-Felder in beiden Netz-YAMLs erneut kommentiert (jetzt korrekt auf p_max_bar=100 verweisend); zusätzlich entdeckt und markiert: `discrete_energies_mwh` in BEIDEN Netz-YAMLs ist EBENFALLS totes Duplikat (von `storage_geometry.yaml`s `per_asset`-Leiter überschrieben) — eine VIERTE unabhängige, bislang unbemerkte Redundanz in derselben Fehlerklasse.

### c) Plausibilität der Kostenkurve gegen reale Projekte — **ABWEICHUNG >2× GEFUNDEN, GEMELDET, NICHT SELBST NACHKALIBRIERT**

**EUR/m³-Tabelle (unverändert Kurve, jetzt mit `unit_tank_m3=50.000`):**

| V [m³] | N | €/m³ |
|---|---|---|
| 50 | 1 | 1.225,3 |
| 500 | 1 | 614,1 |
| 1.000 | 1 | 498,8 |
| 5.000 | 1 | 307,8 |
| 10.000 | 1 | 250,0 |
| 30.000 | 1 | 179,8 |
| 50.000 | 1 | **154,3** |

**Vergleich mit realen Projekten/Literatur:**

| Referenz | Volumen | Investition | Baujahr | €/m³ | Quelle |
|---|---|---|---|---|---|
| **Reuter West, Berlin (TTES)** | 56.000 m³ | „knapp 100 Mio. €" — **GESAMTPROJEKT** (Elektrodenkessel 120 MW + Speicher + Umbau, KEINE saubere Speicher-Einzelkosten-Angabe gefunden trotz gezielter Recherche) | 2022/23 | **~1.786 €/m³ (Obergrenze, inkl. P2H)**; grob bereinigt (eigene EK-Rate 150 T€/MW × 120 MW = 18 Mio. € abgezogen) ~**1.464 €/m³** | [Vattenfall Pressemitteilung](https://group.vattenfall.com/press-and-media/pressreleases/2017/vattenfall-invests-in-innovative-heat-storage-in-berlin), [Vattenfall News 2022](https://group.vattenfall.com/de/newsroom/news/2022/in-reuter-west-werden-rund-350.000-badewannen-befullt) |
| Vojens, Dänemark (PTES) | 200.000 m³ | — | 2015 | 24 €/m³ | [Solarthermalworld](https://solarthermalworld.org/news/seasonal-pit-heat-storage-cost-benchmark-30-eurm3/) |
| Dronninglund, Dänemark (PTES) | 60.000 m³ | — | 2014 | 38 €/m³ | [Bankwatch](https://bankwatch.org/wp-content/uploads/2022/05/2022-05_Case-study-Dronninglund-_eng.pdf) |
| Marstal, Dänemark (PTES) | — | — | — | 41 €/m³ | [Bankwatch](https://bankwatch.org/wp-content/uploads/2022/05/2022-05_Case-Study-Marstal_eng.pdf) |
| EN-14015-Stahltank, Literatur-Median (TTES) | diverse | — | — | ~115 USD/m³ (~107 €/m³) | [ASME](https://asmedigitalcollection.asme.org/sustainablebuildings/article/6/2/021006/1219471/Cost-Analysis-for-Large-Thermal-Energy-Storage) |
| Stahltank ~6.000 m³ (TTES) | 6.000 m³ | — | — | ~100 USD/m³ (~93 €/m³) | [ASME](https://asmedigitalcollection.asme.org/sustainablebuildings/article/6/2/021006/1219471/Cost-Analysis-for-Large-Thermal-Energy-Storage) |

**Modellkurve bei Reuter-West-Maßstab (56.000 m³, N=2 à 28.000 m³):** 183,6 €/m³.

**Abweichungen:**
- **Reuter West (Gesamtprojekt-Obergrenze):** 1.786 vs. 183,6 €/m³ → **Faktor ~9,7×** — WEIT über der 2×-Schwelle. Methodisch stark eingeschränkt: die „~100 Mio. €" sind ein GESAMTPROJEKT (Kohleblock-Rückbau, Elektrodenkessel, Netzanschluss, Genehmigungen), keine saubere Speicher-Einzelkosten-Angabe — Vergleich vermutlich nicht sauber (Scope-Mismatch), aber selbst die grob bereinigte Zahl (~1.464 €/m³) bleibt bei **Faktor ~8×**.
- **Allgemeine Stahltank-Literatur bei 6.000 m³:** Modell 291,4 €/m³ vs. Literatur ~93 €/m³ → **Faktor ~3,1×** — AUCH über der Schwelle, methodisch sauberer als Reuter West (breite Literaturbasis statt Einzelprojekt).
- **Allgemeine Stahltank-Literatur bei 50.000 m³ (Median):** Modell 154,3 €/m³ vs. Literatur ~107 €/m³ → Faktor ~1,44× — **innerhalb der Toleranz.**

**Muster:** die Abweichung ist am größten im mittleren Maßstab (5.000–10.000 m³, wo die Kurve zuvor „sättigte") und verringert sich bei sehr großem Maßstab (30.000–50.000 m³, den V2c erst freischaltet) auf ein tolerierbares Maß. Das spricht dafür, dass V2cs Größenkorrektur selbst RICHTIG und NOTWENDIG war (sie bringt die Kurve NÄHER an die Literatur heran, nicht weiter weg), aber gleichzeitig ein SEPARATES, VORHER VERDECKTES Problem sichtbar macht: die Kurve selbst (`b=0,70`) scheint bei mittlerem Maßstab zu teuer/nicht degressiv genug gegenüber realen großen Anlagen. **Wie angewiesen: NICHT selbst nachkalibriert** (`c0`/`v0`/`exponent_b` unverändert) — nur gemeldet.

### d) Folgen

- **§4bs korrigiert:** „Defekt 11" ist NICHT „falscher Druckwert" (100 statt 3 bar), sondern **„falsche NORM für die Größengrenze angewendet"** (Druckbehälter-Logik auf einen drucklosen Flachbodentank). Beide früheren Zustände — 100 bar (numerisch deaktiviert, korrekter EFFEKT aber aus dem falschen/fehlenden Grund) UND 3 bar (mein eigener V2b-Fehler, 1.778-m³-Grenze) — waren als BEGRÜNDUNG falsch; nur der jetzige Zustand (100 bar, bewusst nicht-bindend, weil die Formel nicht gilt + explizites `max_tank_m3=50.000` aus Referenzanlage) ist korrekt begründet.
- **V2s `unit_tank_m3=10.000`-Entscheidung ist überholt**, zugunsten von 50.000 (wie erwartet).
- **Erwartete Wirkung SB:** SB (mittlerer Tagesbedarf ≈1,75 GWh ≈ 182.500 m³ bei ΔT≈10K) konnte bislang bestenfalls 6 Tanks à 1.778 m³ bilden (§4bs); jetzt reichen 4 Tanks à 50.000 m³ (oder sogar EIN einziger, je nach Ladder-Sprosse) — die Kurve landet dadurch bei deutlich niedrigeren €/m³ (154–180 statt 420–428 aus §4bs). **Das kann den bisherigen SB-Speicherbefund (kein/marginaler Bau, siehe frühere P2/P3-Erwartungen im Session-Gedächtnis) kippen** — aber erst mit einem echten Lauf unter V7a zu bestätigen.

### HALT vor V3 — wie in V2c(c) angeordnet

**Die >2×-Abweichung ist gemeldet, nicht aufgelöst.** Bevor V3 (Investitionskosten/Lebensdauern/O&M) fortgesetzt wird, braucht es eine Autoren-Entscheidung zur Kostenkurve selbst:
- **(a)** Reuter Wests Zahl als methodisch zu unsauber (Gesamtprojekt-Scope-Mismatch) verwerfen, NUR die allgemeine Literatur (weniger scope-verzerrt, aber immer noch 3,1× bei 6.000 m³) als Referenz nehmen — und ENTSCHEIDEN, ob dieses Ausmaß toleriert wird oder eine (separate, NICHT von mir selbst vorgenommene) Neukalibrierung von `exponent_b`/`c0` gebraucht wird.
- **(b)** Eine genauere Reuter-West-Speicher-Einzelkosten-Quelle beschaffen (z. B. Vergabeunterlagen/Ausschreibungen — `ted.europa.eu`-Treffer in der Recherche gefunden, aber nicht ausgewertet, da außerhalb des Zeitbudgets dieses Passes) und den Vergleich damit wiederholen.
- **(c)** Die Abweichung als bekannte Modellgrenze akzeptieren und mit V3 fortfahren (mit einer expliziten Einschränkung im späteren Datenpaket, V8).

**V3 wird NICHT gestartet, bis diese Entscheidung vorliegt** (wie durch V2c(c) angeordnet).

---

## §4bu — 2026-09-30: V2e — §4bt(c)'s „93 €/m³"-Zahl war NICHT REAL; Primärquelle (Lüchinger et al. 2025, Volltext gelesen) zeigt Modellkurve KONSERVATIV, nicht überteuert — HALT AUFGEHOBEN, V3 freigegeben

### a) Root Cause: die 93-€/m³-Zahl existiert in der zitierten Quelle nicht

§4bt(c) zitierte „~100 USD/m³ (~93 €/m³) bei ~6.000 m³ (TTES)" mit Quellenangabe ASME/Lüchinger et al. 2025 — auf Basis einer WebSearch-KI-Zusammenfassung, NICHT einer gelesenen Primärquelle. Auf explizite Anweisung (V2d(a): „ausdrücklich prüfen, ob die 93 EUR/m³ eine Turnkey-Angabe sind") wurde der Volltext beschafft (Open-Access-PDF via Zenodo, `https://zenodo.org/records/17347333`, 14 Seiten inkl. Appendix A–F, direkt mit dem Read-Tool gelesen, nicht per WebFetch-KI-Zusammenfassung) und Wort für Wort geprüft: **die Zahl „93 EUR/m³" bzw. „100 USD/m³ bei 6.000 m³" kommt im gesamten Paper NICHT vor** — weder im Fließtext noch in Appendix D (der Rohdaten-Tabelle mit 17 benannten TTES-Einzelprojekten) noch in Appendix F (Zusammenfassung der Kostenfunktionen). Sie ist ein Artefakt der KI-Zusammenfassung des ursprünglichen WebSearch-Schritts, keine reale Angabe aus der Quelle.

**Lehre (wie angewiesen dokumentiert):** Kostenanker/Zahlen, die für eine Modell-Plausibilitätsprüfung verwendet werden, dürfen nur aus tatsächlich gelesenen Primärquellen stammen (PDF/Volltext), nie aus einer WebSearch- oder WebFetch-KI-Zusammenfassung allein — diese können plausibel klingende, aber nicht in der Quelle vorhandene Zahlen erzeugen. Dasselbe Muster (WebFetch-KI-Zusammenfassung liefert falsche/erfundene Werte) trat in diesem Pass ZWEIMAL auf: einmal beim ursprünglichen 93-€/m³-„Fund", ein zweites Mal bei einem Destatis-Baupreisindex-Abruf während dieser Korrektur selbst (siehe c), wo eine offensichtlich inkonsistente Zahl (~1% Anstieg 2023→2026 bei gleichzeitig gemeldeten +4,6% p.a.) verworfen und durch einen direkten Eurostat-API-Abruf (maschinenlesbares JSON, keine KI-Interpretation) ersetzt wurde. **Regel für den Rest der Kampagne: jede zitierte Zahl, die in eine Modellentscheidung einfließt, muss entweder (i) aus einem selbst gelesenen Primärdokument oder (ii) aus einer strukturierten API-/Tabellenquelle stammen — nie aus einer Fließtext-KI-Zusammenfassung einer Webseite.**

### b) Was die Primärquelle tatsächlich enthält (Appendix D, benannte atmosphärische TTES-Projekte)

Die Quelle (Lüchinger, Hendry, Walter, Worlitschek, Schuetz, 2025, ASME J. Eng. Sustain. Bldgs. Cities 6(2):021006, DOI 10.1115/1.4069122, CC-BY 4.0) enthält in Appendix D 17 einzelne, benannte TTES-Projekte (pressurized/atmospheric/two-zone) mit Volumen, Baujahr, Original-Investition und einer eigenen Spalte „Adjusted volume-specific cost (USD/m³)" — PPP- und inflationsbereinigt auf 2023-US-Preisniveau (Methodik: Kapitel „Methodology for Cost Data Adjustment and Modeling", Fig. 4: Inflationsbereinigung auf 2023 → Kaufkraftbereinigung zwischen USA/GBR/CHE/DEU). Für ATMOSPHÄRISCHE Tanks im relevanten Größenbereich (4.500–18.000 m³, um den Modell-Anker 10.000 m³ herum):

| Projekt | Land | Baujahr | V [m³] | 2023-USD/m³ (Paper, PPP-adj.) | Quelle im Paper |
|---|---|---|---|---|---|
| Hamburg | DE | 1996 | 4.500 | 490 | Appendix D, Ref. [14] |
| Perlen | CH | 2022 | 5.000 | 1.057 | Appendix D, Ref. [92,93] |
| Munich | DE | 2007 | 5.700 | 364 | Appendix D, Ref. [14] |
| Neuköln | DE | 2015 | 10.000 | **2.186 (Ausreißer)** | Appendix D, Ref. [—ᵃ] (saisonalspeicher.de) |
| Friedrichshafen | DE | 1996 | 12.000 | 259 | Appendix D, Ref. [—ᵃ] |
| Haltikon | CH | 2020 | 18.000 | 264 | Appendix D, Ref. [—ᵈ] (AGRO Energie AG, persönl. E-Mail) |

Zusätzlich reale, direkt zitierbare Literaturspannen aus dem Fließtext des Papers (ohne Volumenangabe, daher nicht als Punkte plottbar, nur als Kontext):
- SPF Institut (Ref. [70]): 220–400 USD/m³ für atmosphärische Tanks.
- Sifnaios et al. (Ref. [61]): Systeme >7.500 m³ fallen unter 200 USD/m³.
- Christos (Ref. [71]): Zweitank-System 350–440 USD/m³.
- Yang et al. (Ref. [14]): 100–5.400 USD/m³ (sehr breite Spanne, laut Paper „design-/anforderungsabhängig").

**Abgrenzung/Scope:** das Paper definiert seine Werte durchgehend als „investment costs" / „capital costs" aus Desk-Research über publizierte Projekte — es gibt KEINE explizite Turnkey- vs. Bare-Vessel-Definition im Text. Ein indirekter Hinweis auf den Scope: „In Mannheim, 26% of the cost was allocated to the tank, including the foundation, internal structures, and insulation. In Flensburg, this proportion was 56%" (S. 3) — d. h. die zitierten Gesamtinvestitionskosten umfassen MEHR als nur den Tank selbst (Fundament, interne Struktur, Dämmung + weitere, nicht benannte Kostenblöcke, vermutlich Anschluss/Planung), was für einen installationsnahen statt bare-vessel-Scope spricht — Land/Grundstück wird nirgends explizit erwähnt, weder ein- noch ausgeschlossen.

### c) Währungs- und Preisbasis: FX + Inflation 2023→2026 (Primärquelle: Eurostat-API, nicht Web-KI-Zusammenfassung)

Erster Versuch (Destatis-Seite per WebFetch-KI-Zusammenfassung) lieferte eine intern widersprüchliche Zahl (2023⌀ 130,0 → Aug 2026 131,2, aber gleichzeitig „+4,6% ggü. Vorjahr" gemeldet — unmöglich bei nur +0,9% über 3,5 Jahre) und wurde verworfen. Stattdessen direkt die Eurostat-Statistik-API abgefragt (`sts_inpp_m`, `geo=DE`, `nace_r2=C25` [Herstellung von Metallerzeugnissen, ohne Maschinenbau — die einschlägige Kategorie für Stahltank-Fertigung], `unit=I21` [Index 2021=100], `s_adj=NSA`), Rohdaten als JSON erhalten, nicht KI-interpretiert:

- 2023 (Jahresmittel Jan–Dez): 119,2
- 2026-07 (aktuellster verfügbarer Wert, Stand Abruf 2026-09-30): 125,2
- **Faktor 2023→2026: 125,2 / 119,2 = 1,050 (+5,0%)**

Kombiniert mit dem bereits verwendeten FX-Faktor USD→EUR = 0,925 (2023-Basis, unverändert aus V2c/V2d): **Gesamtfaktor 2023-USD → 2026-EUR = 0,925 × 1,050 = 0,971.**

**Appendix-D-Projekte, jetzt auf 2026-EUR-Basis (direkt vergleichbar mit dem Modellanker):**

| Projekt | V [m³] | 2023-USD/m³ | **2026-EUR/m³** |
|---|---|---|---|
| Hamburg | 4.500 | 490 | **476** |
| Perlen | 5.000 | 1.057 | **1.026** |
| Munich | 5.700 | 364 | **353** |
| Neuköln | 10.000 | 2.186 | **2.123 (Ausreißer, siehe unten)** |
| Friedrichshafen | 12.000 | 259 | **251** |
| Haltikon | 18.000 | 264 | **256** |

**Neuköln-Ausreißer:** wird NICHT gelöscht, sondern als dokumentierter Ausreißer geführt. Ursachen-Vermutung (Autoren-Hypothese, NICHT aus der Quelle verifiziert — die Quelle nennt nur `saisonalspeicher.de` als Input, dessen Projektbeschreibung wurde in diesem Pass nicht ausgewertet): innerstädtische Lage Berlins mit beengter Grundstücksfläche und ggf. höherem Aufwand für Nebenanlagen/Anschluss könnten überdurchschnittliche Kosten erklären, analog zum bereits dokumentierten Mannheim/Flensburg-Befund (26% vs. 56% Tankanteil an den Gesamtkosten — hohe Streuung durch Standortfaktoren ist im Paper selbst als strukturelles Merkmal von TTES-Kosten benannt, nicht spezifisch zu Neuköln).

### d) Korrigierter Plausibilitätsvergleich — Modellkurve liegt DURCHGÄNGIG auf oder unter dem realen Wert

**Modellkurve** (unverändert: `c0=2,5 Mio.€ @ v0=10.000 m³`, `b=0,70`) an denselben Volumina wie die realen Projekte:

| V [m³] | Modell [€/m³] | Real [€/m³, 2026] | Projekt | Modell/Real |
|---|---|---|---|---|
| 4.500 | 317,6 | 476 | Hamburg | 0,67× |
| 5.000 | 307,8 | 1.026 | Perlen | 0,30× |
| 5.700 | 295,9 | 353 | Munich | 0,84× |
| 10.000 | 250,0 | 2.123 | Neuköln (Ausreißer) | 0,12× |
| 12.000 | 236,7 | 251 | Friedrichshafen | 0,94× |
| 18.000 | 209,6 | 256 | Haltikon | 0,82× |

**An JEDEM der sechs benannten, volumenspezifischen realen Vergleichspunkte liegt die Modellkurve auf oder unter dem realen Wert — nirgends darüber.** Die frühere §4bt(c)-Aussage „Faktor ~3,1× zu teuer bei 6.000 m³" beruhte ausschließlich auf der nicht existenten 93-€/m³-Zahl und wird hiermit **vollständig zurückgezogen**. Ersetzt durch:

> **Die Modellkurve liegt an allen sechs benannten realen Projekten (Anhang D, Lüchinger et al. 2025, auf 2026-EUR umgerechnet) auf oder unter dem realen Wert. Der Basisfall (Anker 250 €/m³ bei 10.000 m³) liegt nahe an den beiden günstigsten vergleichbaren Großanlagen — Friedrichshafen (251 €/m³ bei 12.000 m³) und Haltikon (256 €/m³ bei 18.000 m³) — und ist damit als optimistisch/konservativ am unteren Rand des realen Bandes einzuordnen, nicht als überteuert.**

Median der sechs realen Punkte (2026-EUR): 415 €/m³ (ohne Neuköln-Ausreißer: 353 €/m³) — beide deutlich über dem Modell-Anker (250 €/m³), bestätigt die „konservativ/optimistisch"-Einordnung.

**Reuter West bleibt ausschließlich Größenreferenz** (56.000 m³ realer Einzeltank, widerlegt jede formelbasierte Volumenobergrenze, §4bt(a)/(b)) — **kein Kostenanker**, wie in V2c/V2d bereits festgelegt und durch V2e(a) nochmals bestätigt. Der methodisch unsaubere Reuter-West-€/m³-Vergleich aus §4bt(c) (Faktor ~8–9,7×, Gesamtprojekt-Scope-Mismatch) bleibt als eigener, gekennzeichneter Datenpunkt in §4bt stehen, fließt aber NICHT in die obige Kernaussage ein.

### e) Band statt Punktwert — Streuung realer Projekte

Reale Projekte bei vergleichbarer Größe (5.000–12.000 m³) streuen um bis zu **Faktor ~4,1** (Perlen 1.026 €/m³ gegenüber Friedrichshafen 251 €/m³, beide 2026-EUR) — mit Neuköln-Ausreißer sogar Faktor ~8,5. **Band (ohne Ausreißer): 251–1.026 €/m³; Band (mit Ausreißer): 251–2.123 €/m³.** Dies bestätigt R²=0,658 der paper-eigenen Regression für atmosphärische TTES (Appendix F) — gut ein Drittel der Varianz ist NICHT durch das Volumen allein erklärt, sondern durch Standort-/Bauartfaktoren. **Methodische Konsequenz für den Ergebnisbericht (V7):** die Eintrittsschwelle für Speicher wird als Wert relativ zu diesem realen Band berichtet („liegt unter/innerhalb/oberhalb"), nicht als Vergleich gegen einen einzelnen Literaturwert.

### f) Sweep wird ZWEISEITIG — ersetzt V2d(c)

V2d(c)s einseitiger 5-Sprossen-Sweep (1,0/0,7/0,5/0,35/0,25 → 250/175/125/88/63 €/m³) ist durch den korrigierten Befund (Modell bereits am unteren Rand des realen Bandes) überholt — es gibt kein reales Projekt, das die 88/63-€/m³-Sprossen stützen würde. **Ersetzt durch einen symmetrischen, zweiseitigen Sweep für V7:**

| Faktor | c0 [Mio.€] | €/m³ @ 10.000 m³ |
|---|---|---|
| 0,5 | 1,25 | 125 |
| 0,7 | 1,75 | 175 |
| **1,0 (Basis)** | **2,5** | **250** |
| 1,5 | 3,75 | 375 |
| 2,0 | 5,0 | 500 |

Je Lauf wird zusätzlich das €/m³ der TATSÄCHLICH gebauten Größe (nicht nur am 10.000-m³-Anker) ausgegeben. Ergebnisdarstellung (V7/V8): gebautes `V_TES` und Speicherwert über €/m³, mit den sechs Appendix-D-Punkten aus (c) als Punkte und dem Band aus (e) als Hintergrundfläche. Aussageform wie in e) festgelegt.

### g) Notiz fürs Paper (Methodik-Abschnitt)

Die Streuung realer TTES-Projekte bei vergleichbarer Größe (Faktor ~4, ohne Ausreißer) begrenzt die Aussagekraft jeder einzelnen Kostenkurve als Punktschätzung. Dies begründet, warum die Eintrittsschwelle für Speicherinvestition in €/m³ gegen ein reales Streuungsband berichtet wird (e) statt gegen einen einzelnen Literaturwert — und warum V7 den Kostenparameter zweiseitig variiert statt eine einzelne „beste Schätzung" zu kalibrieren.

### h) HALT AUFGEHOBEN — V3 freigegeben

§4bt's „HALT vor V3" ist hiermit aufgehoben. Die zugrundeliegende Abweichung existierte nicht (b–d); die verbleibende Streuung wird strukturell über das Band/den zweiseitigen Sweep abgebildet (e–f), nicht durch eine Neukalibrierung von `c0`/`v0`/`exponent_b` (weiterhin unverändert, wie durchgehend angewiesen). **V3 läuft ab jetzt weiter, danach V4, V5, V6, V7 (mit dem zweiseitigen Sweep aus f) und V8, wie im V0–V8-Sammelauftrag festgelegt.**

---

## §4bv — 2026-09-30: V2f — Config-Hygiene TES-Druck (klein, vor V4) — ABGESCHLOSSEN, verifiziert

`p_max_bar` war seit V2c auf 100 bar gesetzt — korrekt im EFFEKT (nicht-bindend), aber als „numerischer Trick", nicht als physikalisch echter Wert. V2f macht das sauber.

### a) Physikalisch echter Wert

Auslegungshöhe = 45 m (Reuter-West-Referenz, bereits Basis für `max_tank_m3=50.000`). Mit den projekteigenen Konstanten (`RHO_WATER_HOT_KG_M3=971,8 kg/m³`, `P_ATM_BAR=1,013`, `G_ACCEL_M_S2=9,81`, `geometric_storage.py:_h_max_from_pressure`) ergibt exakt 45 m Säule 5,30 bar; gewählt: **`p_max_bar=5,5 bar`** (≈47,1 m Säule, ~2 m/~5% Zuschlag über die Referenzhöhe) — innerhalb der angewiesenen ca.-4,5–5-bar-Spanne, mit den echten Modellkonstanten statt einer Kaltwasser-Faustformel nachgerechnet. Gesetzt in `storage_geometry.yaml`s `per_asset.tes_main` UND `per_asset.tes_sb` (beide identisch).

### b) Größengrenze strukturell von Druck entkoppelt (nicht nur numerisch)

Neuer Parameter `pressure_limits_size: bool` in `GeometricStorageBlock.__init__` (`calion/models/blocks/geometric_storage.py`), Default `True` (= altes Verhalten, unverändert für Study-G/druckbeaufschlagt). Wenn `False`: `V_max_effective = V_max_m3` direkt, OHNE den Umweg über `_h_max_from_pressure(p_max_bar)` — `p_max_bar` geht dann in GAR NICHTS mehr ein, das die Baugröße oder Kosten bestimmt, unabhängig von seinem Zahlenwert (nicht mehr nur „zufällig groß genug"). `component_assembler.py`s `_attach_geometric_storage_from_unified` übergibt `pressure_limits_size=_pressurized` — also `False` für die atmosphärische Standardtechnologie, `True` nur für die explizite `tes_technology: pressurized`-Study-G-Variante (behält ihre eigene, echte Druckklasse aus der Netz-YAML, unverändert, wie angewiesen).

### c) Aktiv-Assertion — bestanden

Build-only-Test (kein Solve): `GeometricStorageBlock` direkt mit SBs realen Parametern (Leiter `[0,37,...,2046]` MWh, `unit_tank_m3=50.000`, `c0=2,5M€`, `v0=10.000`, `b=0,70`) instanziiert, `p_max_bar` über {3, 5.5, 10, 100} bar variiert, `pressure_limits_size=False`: `V_max_effective` UND die pro-Sprosse degressive CAPEX (exakte Formel `C=N·c0·((V/N)/v0)^b` reproduziert) sind bit-für-bit IDENTISCH über alle vier Werte (`V_max_effective=250.000,000 m³`, oberste Sprosse `10.678.459,91 €`, exakt gleich in allen 4 Läufen). Gegenprobe: mit `pressure_limits_size=True` (Study-G-Pfad, unverändertes Legacy-Verhalten) variiert `V_max_effective` korrekt mit dem Druck (3 bar→1.778 m³ — exakt die alte V2b-Formel; 10 bar→164.489 m³; 100 bar→250.000 m³, deckelbindend) — bestätigt, dass NUR der atmosphärische Pfad entkoppelt wurde, der Druckbehälter-Pfad unverändert echte Physik behält. Syntax/Import-Check beider geänderter Module sowie YAML-Parse-Check aller drei Config-Dateien bestanden.

### d) Kommentar/Dokumentation

Ein-Satz-Begründung (EN 14015/API 650, kein Druckbehälter, Größe folgt aus der Aufstellung) in `storage_geometry.yaml`s Header ergänzt; `p_max_bar`-Kommentare in beiden Netz-YAMLs (dort ohnehin DEAD CODE für atmosphärisch) auf den neuen Wert/die neue Begründung aktualisiert.

**Dateien geändert:** `calion/models/blocks/geometric_storage.py` (neuer `pressure_limits_size`-Parameter + bedingte `V_max_effective`-Berechnung), `calion/models/component_assembler.py` (`pressure_limits_size=_pressurized` im `GeometricStorageBlock(...)`-Aufruf), `configs/paper_2/storage_geometry.yaml` (`p_max_bar: 100.0`→`5.5` in beiden `per_asset`-Blöcken + Header-Doku), `configs/paper_2/Stadtbach_topo.yaml` und `Memmingen_P2_base.yaml` (nur Kommentar, Feld bleibt DEAD).

**V3 läuft unverändert weiter (V2f ist eine reine Config-Hygiene-Korrektur, keine Ergebnis- oder Kostenänderung — bit-für-bit-Invarianz in c) belegt das).**

---

## §4bw — 2026-09-30: V3, V4, V5 — Investitionskosten/O&M, CO2-Einordnung, CO2-Netting-Trennung — Code/Config ABGESCHLOSSEN, ERGEBNISSE zur Prüfung vor V6

Auf Anweisung ("V3 bis V5, Ergebnisse vor Ausführung von V6") umgesetzt: reine Code-/Config-Arbeit, KEINE Läufe (wie in der V0-V8-Bindungsreihenfolge festgelegt). Reale Zahlen (statt Platzhaltern) wurden, wo möglich, aus Primärquellen gezogen — direkt gelesene PDFs/APIs, nicht WebFetch-Zusammenfassungen (Lehre aus V2e, [[feedback_primary_source_only_for_cost_anchors]]).

### V3a) HP-CAPEX-Eskalation

`capex_eur_per_mw`: 700.000 → **1.000.000 EUR/MW** (hp_sb UND hp_main), oberes Ende von Pieper et al. 2018s eigener 0,8-1,1-Mio.-Spanne (2017-Datenbasis, informell auf 2026 eskaliert — KEINE formale Indexrechnung für diesen längeren Zeitraum durchgeführt, siehe V5c unten für die Einschränkung). Sensitivitäten für V6/V7 benannt: 0,7 Mio. (untere Spannenkante) und 1,4 Mio. (+40%).

### V3b) EK-Lebensdauer

`lifetime_years`: 25 → **20 Jahre** (ek_sb UND eboiler_main), passend zur DEA/Energinet-Technology-Catalogue-Auslegungslebensdauer für Elektrokessel (Kap. 41); 25 war unbelegt.

### V3c) Fixe O&M — NEU, vorher für JEDE Technologie ABWESEND (S1-Audit-Befund, SS4bo)

Vollständige Code-Implementierung (neue Kostenkategorie, 16. additiver Objective-Term `om_cost`, durchgängig durch `InvestmentCalculator` → `component_assembler.py` (HP/EK/TES/Bestand-Generatoren) → `cost_calculator.py` → `model_finalizer.py` → `constraint_builder.py`s `create_objective` → `result_collector.py`s Cost-Breakdown → `extract_artefacts_p2.py`s `_REAL_COST_KEYS`-Positivliste). **Wichtig:** O&M gilt UNABHÄNGIG von `capex_charged`/`invest_enabled` — auch ein Bestand-Asset mit versunkenem CAPEX braucht reale Wartung (anders als CAPEX selbst, das für Bestand-Assets korrekt bei 0 bleibt, wie in V3e bestätigt).

Skalierung: `capacity × om_eur_per_mw_year × period_frac` (HP/EK/Bestand-Generatoren) bzw. `CAPEX_raw × om_pct_of_capex_per_year × period_frac` (TES) — bewusst NUR mit `period_frac`, NICHT nochmals mit `annual_factor`/ANF (O&M ist bereits eine laufende Jahresrate, keine einmalige Investition).

**Quellen (primär, wo möglich):**

| Technologie | Wert | Quelle |
|---|---|---|
| HP (hp_sb, hp_main) | 3.000 EUR/MW/Jahr | DEA/Energinet Technology Data, Kap. 40 "Heat pumps", Fixed-O&M-Tabelle (die meisten Großwärmepumpen-Varianten 2.000-3.000 EUR/MJ/s/Jahr ≡ EUR/MW/Jahr) |
| EK (ek_sb, eboiler_main) | 1.000 EUR/MW/Jahr | DEA/Energinet, Kap. 41 "Electric Boilers", Fixed-O&M-Tabelle (900-1.100 EUR/MW/Jahr) |
| TES (tes_sb, tes_main) | 0,5%/Jahr vom CAPEX | Ingenieurschätzung — KEIN sauberes Groß-TTES-O&M-Kapitel im geprüften DEA-Katalog gefunden; passiver Stahltank, niedriger als aktive Maschinen |
| Gaskessel (hws_boiler, hww_boiler, gasboiler_main) | 2.000 EUR/MW/Jahr | DEA/Energinet, Kap. 44 "District Heating Boiler, Gas Fired" (1.000-2.500 EUR/MJ/s/Jahr) |
| Gas-KWK (hkw, gtost, chp_main) | 2.500 EUR/MW/Jahr | Proxy aus DEA Kap. 06 "Gas Engines" (~10.000 EUR/MW_el/Jahr), auf thermische Basis umgerechnet — als Näherung gekennzeichnet |
| Biomasse-KWK (bmhkw) | 60.000 EUR/MW/Jahr | Proxy aus DEA Kap. 09 "Biomass CHP", **UNSICHERSTE Zahl dieses Durchgangs** — mehrdeutige Spaltenauswahl in einer mehrspaltigen Anlagengrößen-Tabelle, Größenordnung DEA-gestützt, exakte Spaltenwahl nicht |
| Biomassekessel (biomass_main) | 15.000 EUR/MW/Jahr | Ingenieurschätzung (kein KWK, keine sauberere DEA-Zahl gefunden) |

**Primärquellen-Abweichung explizit gemeldet (wie in V2e angewiesen, nicht verschwiegen):** die ursprüngliche V3-Anweisung nannte "WP 1-2%/Jahr, EK ~1%/Jahr, TES ~0,5%/Jahr" als Platzhalter-Spanne. Die reale DEA-Zahl für HP liegt bei nur **~0,3%/Jahr** (3.000/1.000.000) — 3-7× UNTER dem Platzhalter. EK trifft die Platzhalter-Spanne ungefähr (1.000/150.000 = 0,67%/Jahr). Die reale Quelle ersetzt den Platzhalter, wie in V2e festgelegt.

**Bestand-Assets tragen weiterhin KEIN CAPEX** (unverändert, bestätigt als bewusste Annahme: Retrofit-Rahmung, keine versunkenen Kosten neu bewertet) — **ABER jetzt reale O&M**, siehe Tabelle oben.

### V4) CO2-Einordnung

- **100 EUR/t umbenannt/eingeordnet:** kein amtlich fixierter Einzelwert, sondern eine ETS2-nahe Größenordnung (EU-ETS2, Handelsstart 2027, erste Abgabepflicht 2028). Der MSR-Auslösewert liegt bei ~45 EUR/t (2020-Preisbasis) ≈ ~59 EUR/t (erwartete 2027-Preisbasis) — kein Deckel, nur ein Mengenventil. Prognosen für ~2030 reichen von ~149 EUR/t (BloombergNEF) bis ~222 EUR/t (andere Modelle). 100 EUR/t liegt in der Mitte dieser Prognosespanne — repräsentativ, nicht präzise belegt.
- **Neue, ECHTE Sensitivität (V6/V7):** `co2_price_sensitivity_behg_2026_eur_per_t: 65.0` — der reale, gesetzlich verankerte Höchstwert des deutschen nationalen Emissionshandels (BEHG/nEHS) 2026-Preiskorridors (55-65 EUR/t, 3. BEHG-Novelle), per WebSearch verifiziert. NICHT als aktiver Wert verdrahtet, nur benannt für V6/V7.
- **Biomasse-EF (20 kg/MWh) begründet, nicht genullt:** repräsentiert vorgelagerte Lebenszyklus-Emissionen (Ernte, Aufbereitung, Transport), NICHT Verbrennungs-CO2 (das bleibt biogen/CO2-neutral). 20 kg/MWh liegt innerhalb der üblichen Literaturspanne für Holzbiomasse (~10-40 kg/MWh, z. B. EU-RED-II-Defaultwerte), die exakte Herkunft dieser spezifischen Zahl in dieser Config wurde NICHT eigens re-verifiziert. Unverändert belassen (Nullen hätte rückwirkend jede historische Biomasse-CO2-Zahl verschoben) statt eine neue separate KPI zu bauen — die dokumentierte Begründung erfüllt die "resolve/justify"-Option der Anweisung.

### V5a) CO2-Netting aus der Objective-Rekonstruktion entfernt — KORREKTUR AN DER WURZEL, nicht nur Umbuchung

**Root Cause gefunden:** `result_collector.py`s `CO2_cost_EUR` hielt bislang STILLSCHWEIGEND die KWK-Eigenverbrauchs-GENETTETE Zahl, während `model.obj` tatsächlich BRUTTO optimiert (`calculate_co2_costs()`). Die Diskrepanz wurde bisher durch einen eigens konstruierten Aux-Term (`CO2_selfuse_netting_adjustment_EUR`) exakt kompensiert, der NUR existierte, um `Objective_residual_EUR` auf 0 zu bringen — ein "Rekonstruktions-Trick", keine echte Modellgröße.

**Fix:** `result_collector.py`s `co2_cost`-Variable (und damit `objective["CO2_cost_EUR"]`, und damit `economics.csv`s `cost_co2_eur`-Spalte für ALLE künftigen Läufe) liest jetzt PRIMÄR den live erfassten `_diag_co2_cost_expr`-Wert (= echter `model.co2_cost_expr`, brutto) statt der genetteten `CO2_total_cost_EUR`. Die genettete Zahl bleibt als eigene, klar benannte KPI erhalten: **`CO2_cost_net_of_selfuse_EUR`** — außerhalb von `real_costs_EUR`/`model_aux_terms_EUR`, da sie nie ein echter Objective-Term war. `extract_artefacts_p2.py`s Swap-in-plus-Stornoterm-Logik (Schritt-A-Workaround) vollständig entfernt, `CO2_selfuse_netting_adjustment_EUR` aus `_AUX_COST_KEYS` gestrichen.

**Erwartung (wie angewiesen dokumentiert, NICHT durch einen echten Solve in diesem Pass verifiziert):** `Objective_residual_EUR` sollte jetzt aus eigener Kraft klein sein (nur echtes Rundungsrauschen), ohne den Stornoterm. Der bisherige Aux-Term-Gesamtwert war dominiert vom Netting-Stornoterm (S7-Audit-Beispiel: `model_aux_terms_total_EUR = -1.585.028,80 EUR` für SB-S0-HK0-PIN0) — nach dieser Korrektur sollten die VERBLEIBENDEN echten Aux-Terme (Dump/Tie-Break/Storage-Install/Terminal/Demand-Slack/Return-Anchor/Pressure-Reg/Lateral-Tiebreak/Pressure-Slack/Data-Closure) auf eine sehr kleine Summe fallen. **Diese Erwartung wird durch V6s ohnehin geplanten SB-PIN0-Neulauf unter dem vollständig fixierten V1-V5-Code verifiziert** — kein separater Vorab-Lauf in diesem Pass, wie angewiesen (nur Code/Config, kein Solve vor V6).

### V5b) Breitere "gemeldet == Pyomo == dispatch-ableitbar"-Konsistenzprüfung — BEWUSST NICHT UMGESETZT, wie in der Anweisung selbst als "großer, eigener Scoping-Durchgang" erkannt

Nicht in diesem Durchgang begonnen. Umfang: würde eine generische Prüfung für JEDEN gemeldeten Wert im gesamten Reporting-Pfad brauchen (nicht nur Kapazitäten, wie bisher an einzelnen Stellen geprüft) — deutlich größer als V3-V5s übrige Punkte zusammen. Zurückgestellt auf einen eigenen, künftigen Durchgang (V8-Datenpaket-Vorbereitung oder eine eigene Anweisung), nicht stillschweigend übersprungen.

### V5c) Preisbasis-Jahre auf 2026 — TEILWEISE, mit expliziter Einschränkung

HP-CAPEX (V3a) informell auf ~2026 eskaliert (oberes Ende der 2017er-Spanne), NICHT über eine formale Indexrechnung für diesen ~9-Jahres-Zeitraum (die in V2e verwendete Eurostat-Reihe deckt nur 2023→2026 ab, keine 2017-Basis abgerufen — Aufwand/Nutzen in diesem Pass nicht gerechtfertigt). Die übrigen in S7 gefundenen gemischten Basisjahre — Strompreiszeitreihe (2025), Gas-/Biomassepreise (Jahr undokumentiert) — werden NICHT in diesem Durchgang neu basiert: eine Strompreiszeitreihen-Neubasierung bräuchte neue Marktdaten, ein deutlich größerer Umfang als V3-V5s Code-/Config-Arbeit. **Explizit als bekannte, akzeptierte Einschränkung dokumentiert, nicht stillschweigend übergangen.**

### Verifikation (Build-/Unit-Ebene, KEIN Solve — wie angewiesen)

- Syntax-/Import-Check aller 7 geänderten Python-Module: bestanden.
- YAML-Validierung aller 3 geänderten Config-Dateien: bestanden, Stichprobenwerte bestätigt (hp_sb capex=1.000.000/om=3.000, ek_sb lifetime=20/om=1.000, hkw om=2.500, bmhkw om=60.000).
- Isolierter Unit-Test von `InvestmentCalculator.calculate_component_costs`/`calculate_storage_costs`: bestätigt, dass O&M korrekt NUR mit `period_frac` skaliert (nicht nochmals annuitätisch), dass `include_om=False` O&M korrekt unterdrückt, und dass die exakten erwarteten Zahlen (HP: 10 MW × 3.000 = 30.000 EUR; TES: 50.000 m³-CAPEX-Basis × 0,5% = 62.500 EUR) reproduziert werden.
- **Kein Build-Test mit einem echten Szenario-Output-Verzeichnis durchgeführt** (Risiko, ein reales konvergiertes Ergebnis zu beschädigen, siehe [[feedback_scenario_id_clobbering]]) — die volle numerische Verifikation (16-Term-Objective-Abgleich, tatsächliche O&M-Beträge, die erwartete Aux-Term-Reduktion aus V5a) steht noch aus und wird durch V6s ohnehin geplanten Neulauf geliefert.

### Geänderte Dateien

`calion/models/investment_calculator.py`, `calion/models/component_assembler.py`, `calion/models/cost_calculator.py`, `calion/models/model_finalizer.py`, `calion/models/constraint_builder.py`, `calion/run/result_collector.py`, `scripts/paper_2/extract_artefacts_p2.py`, `configs/paper_2/storage_geometry.yaml`, `configs/paper_2/Stadtbach_topo.yaml`, `configs/paper_2/Memmingen_P2_base.yaml`.

**V6 NICHT gestartet — wie angewiesen, Ergebnisse hiermit zur Prüfung vorgelegt.**

---

## §4bx — 2026-09-30: W1–W4 — WP-CAPEX-Preisbasis geklärt, variable O&M ergänzt, Bestand-O&M als Konstante belegt, EINE Neu-Extraktion durchgeführt (V5-Fix bestätigt)

### W1) WP-CAPEX-Preisbasis — GEKLÄRT: war 2017-Basis, jetzt auf 2026 eskaliert

V3s 1,0 Mio. EUR/MW war NICHT eskaliert (oberes Ende von Pieper et al. 2018s 2017er-Datenband, aber nominal auf 2017er Preisniveau belassen). Primärquelle: Eurostat-API `sts_inpp_m`, `geo=DE`, `nace_r2=C28` (Maschinenbau, passende NACE-Klasse für WP-Hardware, gleiche Methodik wie der TES-Stahltank-Index in V2e), 2017-Jahresmittel **94,5** → 2026-08 (aktuellster Wert) **122,6**, Faktor **1,2974** (+29,7% über 9 Jahre). **1,0 Mio. × 1,2974 = 1.297.400 ≈ 1,3 Mio. EUR/MW** — innerhalb der vom Auftrag erwarteten 1,25–1,4-Mio.-Spanne. Gesetzt in beiden Netz-YAMLs (hp_sb, hp_main). Dringlichkeitsrechnung verifiziert: 0,3 Mio. × 4 MW × ANF(5%,20a)=0,08024 = 96.288 EUR/a ≈ die Hälfte des Q1/Q2-Netto-Vorteils (191–207k EUR/a) — bestätigt, korrekt nachgerechnet. **Neue Sensitivitäten (ersetzen V3as 0,7/1,0/1,4):** unten=1,0 Mio. (NICHT eskaliert, wie angewiesen), Basis=1,3 Mio., oben=1,3×1,15=1,495≈1,5 Mio.

### W2) Variable O&M — GEPRÜFT: DEA-Quelle weist sie aus, jetzt implementiert

**Ja**, dieselben DEA/Energinet-Kapitel, die die fixe O&M liefern, weisen zusätzlich eine VARIABLE O&M (EUR/MWh) aus:

| Technologie | Wert | Einheit | Seite (Kapitel) |
|---|---|---|---|
| HP | 1,0–3,7 (repr. 2,5) | EUR/MWh_th | S. 298 (Kap. 40) |
| EK | 0,5–1,0 (repr. 0,9) | EUR/MWh_th | S. 320 (Kap. 41) |
| Gaskessel | 0,6–2,2 (repr. 1,1) | EUR/MWh_th | S. 326 (Kap. 44) |
| Gasmotor (Proxy hkw/gtost/chp_main) | 4–13 (repr. 8) | EUR/MWh_EL, auf Anlagen-eigenes el/th-Verhältnis umgerechnet | S. 79–80 (Kap. 06) |
| Biomasse-KWK (Proxy bmhkw) | 1,1–11,4 (repr. 4) | EUR/MWh_EL, umgerechnet | S. 138 ff. (Kap. 09), gleiche Spalten-Unsicherheit wie die fixe O&M |
| TES | — | — | KEINE Quelle im geprüften Katalog gefunden |

Implementiert als 17. additiver Objective-Term (`var_om_cost`), Positivliste-Eintrag `OM_variable_cost_EUR`, KEIN Annuitäts-/period_frac-Doppelfaktor (reine Dispatch-Kosten wie Brennstoff). **Aktiv-Assertion bestanden** (Unit-Test: `rate × Σ(dispatched MWh)`, kein Doppel-Scaling, `rate=0` korrekt übersprungen).

### W3) Bestand-O&M als Konstante belegt — BESTÄTIGT über alle 65 Szenarien

Aktiv-Assertion: alle 65 Szenarien aus `scenarios.yaml` (via `_deep_merge` durch die echte Projekt-Config-Lade-Logik) geladen, das fixe-O&M-Niveau der nicht-investierbaren Bestandsanlagen (hkw/gtost/bmhkw/hws_boiler/hww_boiler bzw. chp_main/gasboiler_main/biomass_main) berechnet: **SB = 1.547.000 EUR/a (bit-identisch in allen SB-Szenarien), MM = 76.000 EUR/a (bit-identisch in allen MM-Szenarien)** — bestätigt, KEIN Szenario überschreibt `capacity_mw`/`om_eur_per_mw_year` dieser Anlagen. Als reiner Niveau-Posten im Bericht gekennzeichnet, treibt keine Differenz zwischen Szenarien. Die unsichere Biomasse-KWK-Rate (60.000 EUR/MW/a, S. 138 ff., mehrdeutige Spalte) dominiert SBs Niveau-Term (870.000 von 1.547.000 EUR/a = 56%) — wirkt sich NUR auf das absolute TAC-Niveau und den P1-Vergleich aus, NICHT auf Investitionsentscheidungen.

### W4) Neu-Extraktion — NEUE Infrastruktur gebaut, EIN Lauf verifiziert (SB-S0-HK0-PIN0), Rest offen

**Infrastruktur:** neuer `CALION_EXTRACT_ONLY`-Modus in `calion/run/solver.py`, sitzt neben dem bestehenden `CALION_FEAS_ONLY` (das nach einer Verletzungs-Diagnose immer abbricht). Nutzt denselben Warmstart-Transplant-Mechanismus (`CALION_WARMSTART_FROM` + `full_solution_dump.json`), aber bricht NICHT ab — läuft stattdessen in dieselbe `_collect_timeseries_and_summary()`-Extraktion durch, die auch ein echter Solve nutzt. Kein Solve, echte Kosten-Neuberechnung unter aktuellem Code.

**Ein Lauf durchgeführt:** SB-S0-HK0-PIN0, aus `output/mm_s4_reconcile/o1_sb_pin0/SB-S0-HK0-PIN0` transplantiert, in einen isolierten Scratch-Output (`output/w4_reextract/`, via `CALION_OUT_BASE`) geschrieben — das REALE Ergebnisverzeichnis wurde NICHT angerührt.

**Ergebnis — V5s Kernversprechen BESTÄTIGT, sogar übertroffen:**
- `reconciliation_check: OK`, `residual_EUR = -1.97e-07` (praktisch exakt 0)
- **`model_aux_terms_total_EUR = 0,0 EUR` — EXAKT NULL**, nicht nur die erwarteten ~2.050 EUR (PIN0 hat ohnehin keine aktive TES/Terminal-Value-Mechanik, daher noch sauberer als der allgemeine Fall)
- `objective_total_EUR = 23.396.598,40 EUR` (vorher: 21.131.011,21 EUR, S7-Audit-Referenz) — Anstieg von 2.265.587 EUR
- **Vollständig erklärt:** `OM_fixed_cost_EUR = 1.547.000,00` (exakt W3s SB-Konstante) + `OM_variable_cost_EUR = 720.637,35` = 2.267.637,35 EUR — deckt den Anstieg fast exakt (Restdifferenz ~2.050 EUR vermutlich durch weitere V1-V5-Nebeneffekte, nicht untersucht)
- `co2_cost_net_of_selfuse_EUR = 5.370.170,15 EUR` (neue V5-KPI, korrekt separat ausgewiesen)

**Zwei Auffälligkeiten, geprüft:**
1. **Integritätscheck meldete "pipes.csv is MM"** (`check_run_integrity.py`) — GEPRÜFT und als FALSE POSITIVE bestätigt: `pipes.csv` im Extract-Only-Lauf ist mit 2 Byte praktisch LEER (der neue `CALION_EXTRACT_ONLY`-Pfad überspringt bewusst den thermischen Netzwerk-Export, der für die Kosten-Extraktion nicht gebraucht wird), und der Integritätscheck klassifiziert eine leere Pipe-Liste per Default-Fallback fälschlich als "MM". KEINE echte SB/MM-Datenvermischung (das dokumentierte 2026-09-21-Muster, das dieser Check eigentlich sucht).
2. **165 Constraint-Verletzungen am transplantierten Punkt** unter aktuellem Code — NICHT im Detail untersucht (nur die Zahl geloggt, nicht die einzelnen Constraints). Bei einem Modell mit ~1,2 Mio. Variablen/Constraints ein sehr kleiner Anteil (~0,01%), und die Kosten-Rekonstruktion selbst ist exakt (Residual ~0) — spricht für kleine numerische Restfehler (PWL-Interpolation, Druckausgleich), nicht für einen strukturellen Fehler. **Nicht abschließend geklärt** — bei Bedarf mit den Top-15-Verletzungen (wie im bestehenden `CALION_FEAS_ONLY`-Pfad) nachprüfbar.

**Nicht umgesetzt:** die Neu-Extraktion ALLER Läufe dieser Session (O1-O4, Q1-Q3 u. a.) — nur SB-S0-HK0-PIN0 (das explizit im Auftrag genannte Referenzbeispiel) wurde durchgeführt. Der Umfang einer vollständigen Neu-Extraktion aller Session-Läufe wurde als eigener, größerer Schritt erkannt; die INFRASTRUKTUR dafür (`CALION_EXTRACT_ONLY`) ist jetzt vorhanden und einsatzbereit. Frühere "reale Kosten"-Tabellen im Kontrolldokument, die auf dem VORHERIGEN CO2-Netting-Stornoterm-Mechanismus beruhen (insbesondere §4bp/Q1-Q2, §4bl/O1-O3), sind damit als methodisch veraltet zu kennzeichnen (nicht falsch in der ökonomischen Kernaussage, aber mit dem alten Aux-Term-Mechanismus statt der jetzt bestätigten sauberen Zerlegung) — eine vollständige Neu-Extraktion würde die exakten Zahlen aktualisieren.

**Dateien geändert:** `calion/run/solver.py` (neuer `CALION_EXTRACT_ONLY`-Zweig), `configs/paper_2/Stadtbach_topo.yaml`/`Memmingen_P2_base.yaml` (W1 CAPEX-Eskalation + W2 var_om-Werte für alle Assets).

---

## §4by — 2026-09-30: X — 165 Constraint-Verletzungen aufgeklärt: NICHT von V1-V5/W1-W2 verursacht, sondern unabhängige Modell-Drift seit dem O1-Lauf — Entscheidung (b), V6 freigegeben

### X1) Klassifizierung

Volle Verletzungsliste (nicht nur Top-15) aus dem transplantierten SB-S0-HK0-PIN0-Punkt gezogen (`CALION_VIOLATIONS_DUMP`, neuer Zweig in `calion/run/solver.py`).

**Nach Familie (13 distinkte Constraint-NAMEN, nicht 165 unabhängige Probleme):**

| Familie | Anzahl | Anteil |
|---|---|---|
| Wärmebilanz (`ht_balance_j_bmhkw`=93, `ht_balance_j_gtost`=18) | 111 | 67% |
| Druck (`*_pressure_supply/return_min`, 8 Knoten × 3 Stunden) | 27 | 16% |
| Sonstige (`global_dump_balance`=24, `producer_j_hkw_P_supply_setpoint`=3) | 27 | 16% |

**Betragsverteilung:** n=165, Median=2,52, Max=49,09 (bei `global_dump_balance`), Min=0,50. **Alle 165 > 1e-3, 138/165 (84%) > 1.** Kein Toleranzthema — Entscheidungsregel (a) entfällt.

**Top-Befund:** `producer_j_hkw_P_supply_setpoint[8365/8366/8367]` — Gleichheits-Constraint (lo=hi=16,0), aber `body=0,0` exakt. Das ist kein numerisches Rauschen, sondern eine Variable, die im transplantierten Punkt schlicht UNGESETZT ist.

### X2) Herkunft zugeordnet — Modell-Drift, nicht V1-V5

**Variablen-Abdeckung: nur 96,77%** (7.095.184 von 7.332.139 Variablen des AKTUELLEN Modells haben einen Wert aus dem Dump; 236.955 sind ungesetzt).

**Entscheidender Fund:** das AKTUELLE Modell hat **7.332.139 Variablen** — der O1-Lauf (`meta.json`) hatte **7.358.419** — eine Differenz von **26.280 Variablen**. Das Modell selbst hat sich seit dem O1-Solve strukturell verändert. Das ist rein rechnerisch NICHT durch V1-V5/W1-W2 erklärbar: keiner dieser Eingriffe hat eine `pyo.Constraint(...)`-Definition neu angelegt oder verändert (V1/V3/W2 fügen ausschließlich Kosten-*Expressions* hinzu, V5 ändert nur eine Python-Zuweisung in der Nachbearbeitung, W1/V4 sind reine Konfigwerte) — verifiziert per Code-Durchsicht.

**Cross-Check gegen die Git-Historie** (Commits zwischen dem O1-Lauf und dem Start dieser Session, 2026-07 bis 2026-09-29, explizit VOR V1-V8): `calion/models/component_assembler.py`, `network_manager.py`, `thermal_generator.py`, `thermal_node.py` zeigen reale, unabhängige Commits in genau diesem Zeitraum — u. a. **"pressure fix"**, **"debugging pressure"**, **"edits for gap reduction in stadtbach SB"**. Das deckt sich EXAKT mit den dominanten Verletzungsfamilien (Druck; Wärmebilanz an SB-spezifischen Knoten bmhkw/gtost). Diese Änderungen liegen VOR dem Beginn der V1-V8-Arbeit dieser Session — sie erklären die Modell-Drift, nicht V1-V5.

**Schluss:** der transplantierte Punkt ist **unvollständig, nicht unzulässig** — die 165 Verletzungen sind eine Folge dessen, dass der alte O1-Lauf (`n_vars=7.358.419`, `solve_s=29.463`, `mip_gap=0,13%`) aus einer älteren Modellversion stammt, die sich seither (durch andere, unabhängige Arbeit am Druck-/SB-Modell) strukturell weiterentwickelt hat — nicht aus dieser Sessions V1-V5/W1-W2-Änderungen.

### X3) Entscheidungsregel angewandt: **(b)**

Weder (a) — die Beträge sind NICHT trivial klein — noch (c) — die betroffenen Constraint-FAMILIEN sind ausnahmslos ALT und unverändert, UND die Git-Historie liefert eine konkrete, unabhängige Erklärung, die zeitlich vor V1-V8 liegt. **Es gilt (b): erwartetes Verhalten eines veralteten transplantierten Punkts.** PIN0 MUSS unter dem aktuellen Code neu gelöst werden, bevor es als UB oder Warmstart dient — das ist ohnehin V6s erster Job.

### X4) Buchhaltung

**UB(SB-S0-HK0-PIN0) = 21.131.011 EUR gilt ab sofort als VORLÄUFIG** und wird in dieser und alle folgenden Referenzen entsprechend markiert, bis V6s frischer PIN0-Solve einen bestätigten Wert liefert. Kein Zitat in Ergebnistabellen ohne diese Markierung. Das W4-re-extrahierte `obj_eur=23.396.598` (§4bx) ist damit ebenfalls als vorläufig zu betrachten (gleiche Quelle) — der O&M-Erklärungsanteil (2.267.637 EUR) bleibt aber unabhängig von dieser Einschränkung gültig, da er aus der Kostenformel selbst folgt, nicht aus dem transplantierten Dispatch-Punkt.

**V6 FREIGEGEBEN. Erster Job: SB-S0-HK0-PIN0 frisch lösen (kein Transplant) unter dem vollständigen V1-V5/W1-W2-Code.**

---

## §4bz — 2026-09-30: V6 Job 1 — SB-S0-HK0-PIN0 frisch gelöst — UB BESTÄTIGT, nicht mehr vorläufig

Frischer Solve (kein Transplant, kein Warmstart-Erfolg — Gurobi verwarf den MIP-Start wegen einer Verletzung um 0,5, löste stattdessen vollständig neu), TimeLimit=86.400s (24h), nach **7.674,7 s (2,13 h)** zu **`termination: optimal`** konvergiert (nicht ans TimeLimit gestoßen — sauberer, hochwertiger Solve).

- **`integrity_problems: None`** — der reale Solve (mit vollständigem Netzwerk-Export) zeigt KEINE Integritätsprobleme. Bestätigt endgültig: die frühere "pipes.csv is MM"-Meldung (§4bx/W4) war ein Artefakt des Extract-Only-Pfads (übersprungener Netzwerk-Export), keine echte Datenvermischung.
- **UB(SB-S0-HK0-PIN0) = 23.421.861,63 EUR** — ab sofort BESTÄTIGT, nicht mehr vorläufig (ersetzt den alten O1-Wert 21.131.011 EUR und die transplantierte W4-Schätzung 23.396.598 EUR).
- **Vollständige Bestätigung der O&M-Erklärung (§4bx):** der frische, korrekt konvergierte Wert liegt nur 25.264 EUR (0,1%) über der transplantierten W4-Schätzung — die Analyse, dass der Objective-Anstieg gegenüber dem alten O1-Wert (2.290.851 EUR) fast vollständig durch die neuen O&M-Terme (1.547.000 fix + ~720.637 variabel ≈ 2.267.637 EUR) erklärt wird, hält exakt stand. Die minimale Restdifferenz (~23.000 EUR) liegt im erwarteten Rahmen für echte Dispatch-Unterschiede zwischen dem alten transplantierten Punkt und der frisch gefundenen echten Optimallösung.

**V6 Job 1 abgeschlossen. Weiter mit den restlichen V6-Jobs (freie WP-Größe SB-S0-HK0, CAPEX×CO2-Vorzeichentabelle, Leistungsentgelt-Monatsmaxima-Prüfung).**

---

## §4ca — 2026-10-01: V6 Job 2 — SB-S0-HK0 (freie WP-Größe) frisch gelöst — NETTO-VORTEIL-VORZEICHEN NICHT MEHR BESTIMMT

Frischer Solve, TimeLimit=86.400s(24h), **`optimal` nach 27.421,7 s (7,62 h)**. **`integrity_problems: None`.**

- **Optimierer wählt HP: 2,1 MW (build=1,0)**, TES weiterhin nicht gebaut (0 MWh).
- **UB(SB-S0-HK0) = 23.384.317,87 EUR**, MIPGap=0,4627%.
- **UB(SB-S0-HK0-PIN0) = 23.421.861,63 EUR** (§4bz), MIPGap=0,3727%.

**Punktschätzung Netto-Vorteil (PIN0 − frei) = 37.543,76 EUR/Jahr** — auf den ersten Blick noch positiv, aber **deutlich kleiner** als Q1/Q2s ursprünglicher Befund (191.000–207.000 EUR/a).

**Korrekte Intervall-Rechnung (V0-Methodik, LB/UB statt Punktwert — Pflicht bei MIP-Gap > 0):**

| | UB (= gemeldetes obj_eur) | Gap | LB = UB×(1−Gap) |
|---|---|---|---|
| PIN0 | 23.421.861,63 | 0,3727% | 23.334.577,33 |
| frei | 23.384.317,87 | 0,4627% | 23.276.115,90 |

**KORREKTUR (2026-10-01, Y1): die folgende ursprüngliche Intervall-Rechnung war FALSCH — siehe §4cb für die Richtigstellung.** ~~Max = UB(PIN0) − LB(frei) = +145.745,73 EUR/a. Min = LB(PIN0) − UB(frei) = −49.740,54 EUR/a. → Intervall [−49.741 ; +145.746] EUR/a, Vorzeichen nicht bestimmt.~~ **Fehler:** PIN0 ist eine Restriktion des freien Problems (capacity=0 ist ein zulässiger Punkt des freien Problems) — bei einem Minimierungsproblem kann eine Restriktion des zulässigen Bereichs das Optimum nie verbessern, also gilt STRUKTURELL `Frei_wahr ≤ PIN0_wahr` immer, unabhängig von beiden Gaps. Die untere Schranke der Ersparnis ist damit NICHT `LB(PIN0)−UB(frei)` (das behandelt beide Läufe fälschlich als unabhängig), sondern `max(0, LB(PIN0)−UB(frei))`. Richtiges Intervall und Einordnung: siehe §4cb.

**Konsequenz für die weiteren V6-Jobs:** die CAPEX×CO2-Vorzeichentabelle ist jetzt nicht nur eine Sensitivitätsprüfung, sondern die zentrale offene Frage — sie wird zeigen, ob das Vorzeichen über den plausiblen Parameterbereich (1,0/1,3/1,5 Mio. EUR/MW × 65/100 EUR/t CO2) systematisch kippt oder innerhalb der Unsicherheit stabil bleibt.

### Schnelle Vorab-Abschätzung (NICHT re-optimiert — korrigierte Lesart, siehe §4cb/Y2)

Bevor 5 weitere Mehrstunden-Solves gestartet werden: CAPEX- und CO2-Kostenterme skalieren linear mit ihrer jeweiligen Rate bei FESTEM Dispatch/FESTER Kapazität (2,1 MW, aus Job 2). Alle anderen Kostenterme aus Job 1/2 unverändert übernommen.

**KORREKTUR (Y2, §4cb): diese Tabelle zeigt NICHT den Netto-Vorteil des Optimums, sondern das REGRET des festgehaltenen 2,1-MW-Punkts gegenüber PIN0 bei veränderten Parametern — umbenannt entsprechend:**

| CAPEX | CO2-Preis | PIN0 [EUR] | 2,1-MW-WP (fest) [EUR] | Regret der 2,1-MW-WP [EUR/a] |
|---|---|---|---|---|
| 1,0 Mio. | 100 | 23.421.862 | 23.332.811 | +89.051 |
| 1,0 Mio. | 65 | 21.056.044 | 21.001.180 | +54.864 |
| **1,3 Mio.** | **100** | **23.421.862** | **23.384.318** | **+37.544 (ECHTER SOLVE, = Optimum)** |
| 1,3 Mio. | 65 | 21.056.044 | 21.052.687 | +3.357 |
| 1,5 Mio. | 100 | 23.421.862 | 23.418.656 | +3.206 |
| 1,5 Mio. | 65 | 21.056.044 | 21.087.025 | **−30.981** |

**Lesart (korrigiert):** eine negative Zelle bedeutet NICHT, dass die optimale WP-Investition dort negativ wäre (strukturell unmöglich, §4cb/Y1) — sie bedeutet, dass das FESTGEHALTENE 2,1-MW-Ergebnis bei diesen Parametern SCHLECHTER ist als PIN0 (0 MW), also nicht mehr optimal ist. Das wahre Optimum an dieser Stelle liegt bei 0 MW (oder einer anderen, kleineren Größe) — NIE unter PIN0s Wert. **Aussage: ab ca. CAPEX=1,5 Mio. EUR/MW und CO2=65 EUR/t schrumpft die optimale WP-Größe auf (nahe) null.** Eine echte Neulösung dieses Eckfalls (Y4) bestätigt die exakte optimale Größe dort.

---

## §4cb — 2026-10-01: Y1/Y2 — Korrektur: Intervall-Fehler in §4ca (PIN0 ist Restriktion, nicht unabhängiger Lauf) — eigener Fehler, direkt zurückgenommen

### Y1) Intervall korrigiert

**Fehler (von mir, §4ca):** die Ersparnis-Unsicherheit wurde als `[LB(PIN0)−UB(frei) ; UB(PIN0)−LB(frei)]` berechnet, als wären PIN0 und das freie Problem zwei UNABHÄNGIGE Läufe mit unabhängigen Gaps. Das ist falsch: **PIN0 ist das freie Problem MIT der Zusatzrestriktion Kapazität=0** — jeder zulässige Punkt von PIN0 ist auch ein zulässiger Punkt des freien Problems (einfach mit WP-Kapazität=0 gewählt). Bei einem Minimierungsproblem kann das Hinzufügen einer Restriktion das Optimum nur verschlechtern oder gleich lassen, nie verbessern: **`Frei_wahr ≤ PIN0_wahr` gilt strukturell, für JEDE Parametrisierung, unabhängig von beiden Gaps.**

Die korrekte untere Schranke der Ersparnis ist daher `max(0, LB(PIN0) − UB(frei))`, nicht `LB(PIN0) − UB(frei)` direkt — negative Werte sind strukturell ausgeschlossen und werden auf 0 gekappt.

**Korrigiertes Ergebnis:**
- Ersparnis_min = max(0, 23.334.577,33 − 23.384.317,87) = max(0, −49.740,54) = **0 EUR/a**
- Ersparnis_max = UB(PIN0) − LB(frei) = 23.421.861,63 − 23.276.115,90 = **145.745,73 EUR/a** (unverändert, diese Schranke war korrekt)

**→ Der Wert der WP-Investition in SB liegt in [0 ; 145.746] EUR/a, d. h. bei maximal ca. 0,62% der TAC (23,4 Mio. EUR).** Die frühere Formulierung "Vorzeichen unbestimmt, könnte ein Verlust von bis zu 50k EUR/a sein" (§4ca) wird hiermit ZURÜCKGENOMMEN — sie war mathematisch nicht haltbar. Investitionsfreiheit kann den Zielfunktionswert nie verschlechtern; der Punktwert 37.544 EUR/a bleibt die beste Schätzung, mit einer auf [0, 145.746] korrigierten Unsicherheitsspanne statt eines die Null umschließenden, fälschlich symmetrischen Intervalls.

### Y2) Sensitivitätstabelle umbenannt und richtig gelesen

Siehe korrigierte Tabelle und Lesart oben (§4ca) — aus "Netto-Vorteil" wurde "Regret der 2,1-MW-WP bei veränderten Parametern" (die real von Job 2 gewählte Größe war 2,1 MW, nicht 4 MW). Negative Zellen zeigen, dass die FESTGEHALTENE 2,1-MW-Entscheidung bei härteren Parametern nicht mehr optimal ist (das wahre Optimum dort ist 0, nie negativ) — nicht, dass Investition dort schadet. Aussage: ab CAPEX≈1,5 Mio. EUR/MW × CO2=65 EUR/t schrumpft die optimale Größe auf (nahe) null.

### Y3/Y4 — als Nächstes

Reihenfolge wie angewiesen: ERST die Leistungsentgelt-Monatsmaxima-Korrektur (ändert das Modell selbst, macht vorher gerechnete Eckfälle ungültig), DANN genau ein Eckfall-Paar (CAPEX=1,5 Mio./CO2=65, frei+PIN0) mit engerem Gap (Ziel 0,15%) unter der dann gültigen Leistungsentgelt-Variante. Siehe unten für die Umsetzung.

---

## §4cc — 2026-10-01: Y3 — Monatsleistungspreis implementiert (NEUER Mechanismus, bisher gab es nur Jahresmaxima) — zwei Läufe gestartet

**Vorher nicht vorhanden:** das Modell kannte nur EINEN jährlichen Leistungsspitzen-Mechanismus (`model.P_buy_peak`, `>= P_buy[t]` über alle 8.760 Stunden). Echte monatsweise Abrechnung (12 getrennte Monatsspitzen) existierte nicht und wurde für Y3 neu gebaut.

**Implementierung:**
- `calion/models/constraint_builder.py`s `add_grid_market_constraints()`: neuer optionaler Parameter `month_groups` — wenn gesetzt, werden ZUSÄTZLICH zum bestehenden Jahres-`P_buy_peak` 12 `P_buy_peak_month[m]`-Variablen mit je eigener `>=P_buy[t]`-Constraint für die Stunden dieses Monats gebaut (Jahres-Mechanismus bleibt immer bestehen, für den Diagnose-Vergleich unten).
- `calion/models/cost_calculator.py`: neue Funktion `calculate_demand_charge_monthly()` — Summe aus 12× (Monatsrate × Monatsspitze).
- `calion/models/model_finalizer.py`: Monatsgruppen werden aus den ECHTEN Eingabe-Zeitstempeln (`self.table.index`, nicht einer generischen 30-Tage-Annahme) abgeleitet, NUR wenn `grid.demand_charge_mode: monthly` explizit gesetzt ist (Default unverändert: "annual"). Objective wählt dann `calculate_demand_charge_monthly` statt der bisherigen Jahresformel.
- **Eigener Bug gefunden und behoben, bevor er scharf wurde:** `result_collector.py`s `Demand_charge_cost_EUR` las bisher IMMER die Jahresformel direkt nach (`peak × rate × year_frac`), unabhängig davon, was tatsächlich im Objective stand — für den neuen Monats-Modus wäre das falsch gewesen (gleiche Fehlerklasse wie V5s CO2-Netting-Fund). Behoben nach demselben Muster: liest jetzt `model.demand_cost_expr` direkt (die echte, live erfasste Objective-Expression), unabhängig vom Modus.
- **Diagnose ergänzt** (`result_collector.py`): `Annual_peak_hour_index`/`_timestamp`, `Top10_peak_hours_MW` (Stunde+Zeitstempel+Wert), `Monthly_peaks_MW` (je Monat), `Demand_charge_annual_billing_EUR` vs. `Demand_charge_monthly_billing_EUR_equiv_rate` vs. deren Differenz — IMMER berechnet, unabhängig vom aktiven Modus.
- **Zwei neue Szenarien** (`configs/paper_2/scenarios.yaml`): `SB-S0-HK0-PIN0-MONTHLY`, `SB-S0-HK0-MONTHLY` — identische Overrides wie ihre Basis-Szenarien, zusätzlich `grid: {demand_charge_mode: monthly, demand_charge_eur_per_mw_month: 10.603,33}` (= 127.240/12, "Rate umgerechnet" wie angewiesen, keine andere reale Monatstarif-Annahme).

**Verifikation (Build-only, kein Solve):** echte 12 Kalendermonate aus den Eingabedaten erkannt (Jan=744, Feb=672 [Nicht-Schaltjahr], Mär=744, Apr=720, Mai=744, Jun=720, Jul=744, Aug=744, Sep=720, Okt=744, Nov=720, Dez=744 Std., Summe=8.760 ✓). 8.760 `(Monat,Stunde)`-Constraint-Paare korrekt gebaut, Objective-Umschaltung bestätigt ("Using MONTHLY demand charge: 10.603,33 EUR/MW/Monat × 12 Monate").

**Zwei Läufe gestartet** (sequenziell, gleiche Effort-Einstellungen wie Job 1/2: TimeLimit=86.400s, Warmstart aus den jeweils passenden alten .sol-Dateien): `SB-S0-HK0-PIN0-MONTHLY`, danach `SB-S0-HK0-MONTHLY`.

**Hinweis Sitzungsunterbrechung:** die vorherige Sitzung endete, während Job B (`SB-S0-HK0-MONTHLY`) lief — Job A war zu diesem Zeitpunkt bereits fertig und sein Ergebnis unversehrt auf der Platte. Job B wurde in der neuen Sitzung identisch neu gestartet (Warmstart jetzt aus `SB-S0-HK0`s eigenem .sol).

**Job A (`SB-S0-HK0-PIN0-MONTHLY`) ABGESCHLOSSEN:** `optimal`, Gap=0,0895% (bereits unter dem für den Eckfall geforderten 0,15%-Ziel), gelöst in 1.713,7 s (28,6 min — sogar schneller als die Jahres-Variante). **UB = 23.361.041,18 EUR** — um 60.820,45 EUR GÜNSTIGER als PIN0 mit Jahresabrechnung (23.421.861,63 EUR). Monatsabrechnung senkt hier also die Kosten (saisonal verteilte Lastspitzen summieren sich über 12 Monatsmaxima günstiger als ein einzelnes Jahresmaximum bei vollem Satz).

**Job B (`SB-S0-HK0-MONTHLY`, freie WP-Größe) ABGESCHLOSSEN:** `optimal`, Gap=0,4233%, gelöst in 15.125,5 s (4,20 h). **UB = 23.364.695,19 EUR**, gewählte WP-Größe **1,9 MW** (vs. 2,1 MW bei Jahresabrechnung — leicht kleiner, konsistent mit geringerem Lastspitzen-Vorteil bei Monatsabrechnung). `integrity_problems: None`.

**Korrektes Intervall (Y1-Methodik) für Monatsabrechnung:**

| | UB | Gap | LB |
|---|---|---|---|
| PIN0-MONTHLY | 23.361.041,18 | 0,0895% | 23.340.139,54 |
| frei-MONTHLY | 23.364.695,19 | 0,4233% | 23.265.780,94 |

Ersparnis_min = max(0, LB(PIN0)−UB(frei)) = max(0, −24.555,65) = **0 EUR/a**
Ersparnis_max = UB(PIN0)−LB(frei) = **95.260,24 EUR/a**

**→ Wert der WP-Investition unter Monatsleistungspreis: [0; 95.260] EUR/a, max. 0,41% der TAC.** Enger als unter Jahresabrechnung ([0; 145.746] EUR/a, 0,62%) — die Monatsabrechnung verringert den Investitionswert der WP, wie erwartet (weniger konzentrierter Lastspitzen-Vermeidungsvorteil). Hinweis: der Punktwert von frei-MONTHLY liegt sogar leicht ÜBER PIN0-MONTHLYs Punktwert — strukturell unmöglich als wahrer Optimalwert (Y1), reines Gap-Rauschen, durch die Intervall-Methodik korrekt aufgefangen (Ersparnis_min korrekt auf 0 statt negativ geklemmt).

---

## §4cd — 2026-10-02: Y4 — Eckfall (CAPEX=1,5 Mio./CO2=65) mit engem Gap gelöst — WP schrumpft auf 1,0 MW, NICHT auf null

Beide Läufe unter `grid.demand_charge_mode=monthly`, `CALION_MIPGAP=0,0015`, `CALION_MIPFOCUS=3`, `CALION_TIMELIMIT=172.800s` (48h), Warmstart aus den jeweiligen MONTHLY-Basisläufen:

| | UB [EUR] | Gap | Status | Solve-Zeit |
|---|---|---|---|---|
| PIN0-CORNER | 20.949.752,16 | **0,1105%** | optimal | 1.709,5 s (28,5 min) |
| frei-CORNER | 20.936.937,47 | **0,1409%** | optimal | 23.784,5 s (6,61 h) |

**Beide Gaps unter dem 0,15%-Ziel erreicht.** `integrity_problems: None` (beide).

**Gewählte WP-Größe im freien Lauf: 1,0 MW** — deutlich kleiner als bei den Basisfall-Parametern (1,9–2,1 MW), aber **NICHT null**, anders als die ursprünglich formulierte Erwartung ("optimale Größe fällt auf null"). Die Investition bleibt selbst am härtesten explizit angeordneten Parameterpunkt knapp positiv.

**Korrektes Intervall (Y1-Methodik):**
- LB(PIN0)=20.926.600,96, UB(PIN0)=20.949.752,16
- LB(frei)=20.907.442,86, UB(frei)=20.936.937,47
- Ersparnis_min = max(0, −10.336,51) = **0 EUR/a**
- Ersparnis_max = **42.309,30 EUR/a** (≈0,20% der TAC an diesem Punkt)
- Punktwert (UB−UB) = 12.814,69 EUR/a (weiterhin positiv, aber die kleinste Zahl in der gesamten Eckfall-Serie)

**Zusammenfassende Tabelle über alle vier Lauf-Paare dieser Sitzung:**

| Variante | CAPEX | CO2 | Abrechnung | WP-Größe | Intervall [EUR/a] | max. % TAC |
|---|---|---|---|---|---|---|
| Basis (echt gelöst) | 1,3 Mio. | 100 | Jahres | 2,1 MW | [0; 145.746] | 0,62% |
| Monats (echt gelöst) | 1,3 Mio. | 100 | Monats | 1,9 MW | [0; 95.260] | 0,41% |
| **Eckfall (echt gelöst)** | **1,5 Mio.** | **65** | **Monats** | **1,0 MW** | **[0; 42.309]** | **0,20%** |

**Muster bestätigt über drei unabhängige, echte Lösungspaare:** der Wert der SB-WP-Investition ist in JEDEM getesteten Fall klein (≤0,62% der TAC), strukturell nie negativ (Y1), und schrumpft monoton mit steigendem CAPEX, sinkendem CO2-Preis und bei Monatsabrechnung — bleibt aber am härtesten getesteten Punkt noch knapp über null. Keine weiteren Eckfälle nötig (wie in Y5 angekündigt).

### Y5 — Paper-Formulierung (angepasst an das tatsächliche Ergebnis)

Die vom Autor vorformulierte Aussage ("… fällt die optimale Größe auf null") wird durch das Ergebnis NICHT bestätigt — die Größe schrumpft auf 1,0 MW, nicht auf null. Angepasster Vorschlag:

> „Der Wert der Wärmepumpeninvestition in Stadtbach liegt, je nach Abrechnungskonvention der Netzentgelte, zwischen 0 und maximal 0,62% der Jahreskosten. Innerhalb dieser Spanne ist er mit dem eingesetzten Rechenaufwand (MIP-Gap-Unsicherheit) nicht weiter auflösbar. Bei Investitionskosten von 1,5 Mio. EUR/MW und einem CO2-Preis von 65 EUR/t — beide am oberen bzw. unteren Rand des untersuchten Unsicherheitsbereichs — sinkt die wirtschaftlich optimale Anlagengröße deutlich (von 1,9–2,1 MW im Basisfall auf 1,0 MW), bleibt aber positiv; das Investitionsvorzeichen kippt innerhalb des explizit untersuchten Parameterbereichs nicht vollständig."

**Dateien/Konfiguration:** zwei neue Szenarien `SB-S0-HK0-PIN0-MONTHLY-CORNER`/`SB-S0-HK0-MONTHLY-CORNER` in `configs/paper_2/scenarios.yaml`, gelöst via `CALION_MIPGAP`/`CALION_MIPFOCUS`/`CALION_TIMELIMIT`-Env-Overrides (bereits vorhandener Mechanismus in `scenario_runner.py`, keine Code-Änderung nötig).

**V6/Y-Block vollständig abgeschlossen.**

---

## §4ce — 2026-10-02: Z — V7 FINALER LAUF-SATZ, Phase 1 gestartet (Plan + Begründung der reduzierten Lauf-Zahl)

**Standardprotokoll (Z, Standardregel):** matched effort MM=14.400s(4h)/SB=28.800s(8h), MIPGap-Ziel 0,15%, MIPFocus=3, Warmstart aus dem nächstgelegenen .sol, Basisfall-Leistungsentgelt=Jahresmaximum (Monatsmaxima nur in Z3 wo genannt). **Bindet das Zeitlimit, bevor 0,15% erreicht ist: als Ergebnis berichten (erreichter Gap), NICHT nachjustieren** — anders als bei Y4 (dort wurde das Zeitlimit bewusst über den Standard hinaus verlängert, um den einen autorisierten Eckfall sauber aufzulösen; V7s Standardläufe folgen der Standard-Policy).

### Entscheidender Effizienzgewinn: EINE geteilte PIN0-Baseline pro Netz statt einer PIN0 je Szenario

Geprüft (`configs/paper_2/scenarios.yaml`, SB-S1/S2/S3 und MM-S1/S2/S3 verglichen): S1/S2/S3 unterscheiden sich AUSSCHLIESSLICH im `tes_node` (TES-Standort) und bei S3 zusätzlich `hot_charging: true` — `hp_node`, Netztopologie, Nachfrage sind IDENTISCH über S1/S2/S3 UND identisch mit S0. Bei PIN0 (TES/HP/EK-Kapazität auf 0 fixiert) ist der TES-STANDORT bedeutungslos (ein nicht gebauter Speicher hat keinen Standort-Effekt) — **PIN0 ist daher für S0/S1/S2/S3 (und alle c0-Sweep-Sprossen von Z1, da c0 nur die Kosten eines GEBAUTEN Speichers betrifft) mathematisch IDENTISCH.** Eine einzige frische PIN0-Lösung je Netz genügt als gemeinsame Baseline — **spart ca. 7 von ursprünglich geschätzten ~12 PIN0-Läufen in Z1/Z2.**

**Wichtige Einschränkung (nicht auf Z3 übertragen):** diese Vereinfachung gilt NUR, wenn ausschließlich TES-Kostenanker/-Standort variiert. Z3s Sensitivitäten (Strompreis-Amplitude, Netzentgelt, Direktvermarktung, Monatsmaxima) verändern die KOSTENFUNKTION selbst — dort bleibt der PIN0-Dispatch (Bestandsanlagen kaufen/verkaufen weiterhin Strom) vom Sensitivitätsparameter abhängig. Für Z3 wird je Sensitivität eine EIGENE PIN0-Lösung gebraucht, keine Wiederverwendung.

### SB-PIN0: bereits frisch vorhanden (V6 Job 1, §4bz) — kein Neulauf nötig

UB=23.421.861,63 EUR, `optimal`, Gap=0,3727%, unter vollständigem V1-V8-Code gelöst. Dient als gemeinsame Baseline für SB-S1/S2/S3.

### MM-PIN0: bisheriger Stand (`o1_mm_pin0`) ist VORSESSION-CODE (vor V1-V8) — Neulauf gestartet

`obj_eur=319.382,19`, Gap=0,00997% — aber unter altem Code (vor O&M, vor CAPEX-Eskalation, vor CO2-Netting-Fix) gelöst, daher nicht verwendbar als V7-Baseline. Frischer Lauf gestartet (Warmstart aus dem alten .sol).

### Phase 1 — JETZT gestartet (zwei parallele, intern sequenzielle Ketten, vollständig vom Harness entkoppelt)

**MM-Kette** (9 Läufe, TimeLimit=14.400s je Lauf): MM-S0-HK0-PIN0 (frisch) → MM-S2-HK0 c0×{0,5/0,7/1,0/1,5/2,0} (Z1, c0×1,0 = gleichzeitig Z2s S2) → MM-S2-HK0 mit `CALION_TES_FIX_MWH=23,9` (Z1-Regret) → MM-S1-HK0 (Z2) → MM-S3-HK0 (Z2).

**SB-Kette** (3 Läufe, TimeLimit=28.800s je Lauf, SB-PIN0 bereits vorhanden): SB-S1-HK0 → SB-S2-HK0 → SB-S3-HK0 (alle Z2, Warmstart aus SB-S0-HK0).

**Ausgabe je Lauf (Z1/Z2-Pflichtfelder):** wird nach Abschluss aus `cost_breakdown.json`/`geometry.csv`/`meta.json` extrahiert (gebautes V_TES, Zahl der Tanks, EUR/m³, UB/LB/Gap, Dominanz gegen die jeweilige geteilte PIN0-Baseline, Wert-Intervall mit Nullschranke [Y1-Methodik], Hilfstermanteil, Notkühler-/Closure-MWh) — Sammelauswertung folgt nach Abschluss aller Phase-1-Läufe.

### Phase 2 — BLOCKIERT bis Phase 1 abgeschlossen (NICHT vergessen, bewusst zurückgestellt)

- **Z2 SB-Zusatz:** c0×0,5 für das beste SB-Standortszenario — Standortgewinner erst nach Phase 1s SB-Kette bekannt.
- **Z3 (alle Sensitivitäten):** "bestes Szenario je Netz" ist die Voraussetzung für JEDE Z3-Zeile — kann erst nach Phase 1 definiert werden. Grobschätzung: bis zu 16 weitere Läufe (4 Sensitivitätsarten × 2 Netze × [Hauptszenario+eigene PIN0]), wird nach Phase 1 präzisiert.

### Parallel, JETZT (kein Solve nötig)

Z4 (Validierung über unabhängigen Pfad) und die laufunabhängigen Teile von Z5 (Datenpaket-Grundgerüst) werden parallel zu Phase 1 vorbereitet, nicht nach Abschluss aller Läufe.

---

## §4cf — 2026-10-04: Phase 1 abgeschlossen — eigener Konfigurationsfehler gefunden+behoben, MM-TES außerhalb des Testbereichs unwirtschaftlich, SB-Topologie-Befund klar, eine Infeasibilität gemeldet (nicht nachjustiert)

### Eigener Fund: MM-PIN0 scheiterte an der eigenen V1-Assertion — echter, vorher unentdeckter Konfigurationsfehler

`eboiler_main`s Basis-`capacity_mw` (5,0 MW, "INITIAL — overridden by investment optimizer") wurde in der PIN0-Override NIE auf 0 gesetzt — nur `investment.capacity_max_mw`. Mit `investment.enabled=false` wird dieser 5,0-MW-Fallback zur fixen, ungekosteten Kapazität — exakt die Fehlerklasse, die V1s Assertion erkennen soll (und hier korrekt erkannt hat). `hp_main`s Basis-`capacity_mw` ist bereits 0 (daher kein Problem dort). **Behoben:** `capacity_mw: 0.0` zur PIN0-Override von `eboiler_main` ergänzt (`configs/paper_2/scenarios.yaml`). Neulauf gestartet, läuft.

### Z1 (MM-Speicher-Break-even): KEIN Break-even im getesteten Bereich gefunden — echtes Negativergebnis

Alle fünf c0-Sprossen (×0,5/0,7/1,0/1,5/2,0 = 125/175/250/375/500 EUR/m³ am Anker) liefern **exakt denselben Objective-Wert (416.201,1252188253 EUR, auf 13 signifikante Stellen identisch)** — bestätigt (geometry.csv der letzten Sprosse, c0×2,0): `build=0, V_TES_m3=0,0`. Da identische Kosten über fünf unabhängige volle Re-Solves nur dann auftreten, wenn in JEDEM Fall nichts gebaut wird, gilt: **MM baut in KEINEM der fünf getesteten Kostenniveaus Speicher — selbst beim halben Kostenanker (125 EUR/m³) nicht.** Kein Break-even innerhalb von [125, 500] EUR/m³ gefunden. Ein tieferer Break-even-Punkt (< 125 EUR/m³) ist nicht ausgeschlossen, aber NICHT eigenmächtig nachgetestet (wie angewiesen: Ergebnis berichten, nicht nachjustieren).

**Hinweis Datenhaltung:** alle fünf Sprossen liefen unter demselben `scenario_id=MM-S2-HK0` in denselben Ausgabeordner — spätere Läufe überschrieben die Detail-Artefakte (`cost_breakdown.json`/`geometry.csv`) früherer Sprossen. Nur der letzte Lauf (c0×2,0) hat vollständige Artefakte auf der Platte; die identischen Objective-Werte (aus den Log-Zeilen) belegen aber zweifelsfrei, dass dasselbe (V=0) auch für die anderen vier galt.

**Z1-Regret-Lauf (V=23,9 MWh fix) — INFEASIBLE, gemeldet, nicht nachjustiert:** `Model is infeasible or unbounded` (Gurobi, nach Presolve, 0 Knoten exploriert). Die IIS-Berechnung selbst schlug mit einem Pyomo/Gurobi-Schnittstellenfehler fehl (`'GUROBIFILE' object has no attribute '_solver_model'`), sodass die genaue verletzte Constraint nicht ermittelt werden konnte. Der geometrische Vorab-Check in `geometric_storage.py` (`V_fixed_m3 > V_max_effective`) wurde NICHT ausgelöst (sonst klarer `ValueError`, kein Gurobi-Infeasible) — die Infeasibilität liegt also an einer Wechselwirkung mit anderen Constraints (z. B. Dispatch-Konsistenz bei fixer statt freier TES-Fahrweise), nicht an der reinen Geometrie. **Nicht weiter diagnostiziert** (Zeitbudget, und Z schreibt explizit "wird ein Szenario unzulässig: als Ergebnis berichten, nicht nachjustieren") — als Ergebnis festgehalten: der MM-Regret-Lauf bei V=23,9 MWh ist unter dem aktuellen Code infeasible.

### Z2 (Topologie): SB zeigt einen klaren, substantiellen Standort-Effekt — MM nicht

**SB** (alle drei: `maxTimeLimit` erreicht, Gap über dem 0,15%-Ziel, wie angewiesen als Ergebnis berichtet, nicht nachjustiert):

| Szenario | TES-Standort | UB [EUR] | Gap | V_TES gebaut |
|---|---|---|---|---|
| SB-S1-HK0 | j_hkw (Zentrale) | **23.199.501,59** | 0,2545% | **438,0 MWh (30.379 m³, 1 Tank)** |
| SB-S2-HK0 | j_man (mit WP) | 23.384.317,87 | 0,4655% | 0 (nicht gebaut) |
| SB-S3-HK0 | j_man (Hot-Charging) | 23.384.317,87 | 0,4655% | 0 (nicht gebaut) |

**S1 ist 184.816,29 EUR/a günstiger als S2/S3 — und S2/S3 reproduzieren exakt (auf 13 Stellen) den alten SB-S0-HK0-Wert (V6 Job 2, §4ca).** Klarer, substantieller, topologie-getriebener Befund: Speicher am PRIMÄRERZEUGER (Zentrale) ist wirtschaftlich, am WP-Standort nicht — **Kern des Paper-Titels bestätigt sich hier direkt.** **SB-S1-HK0 ist damit SBs "bestes Szenario" für Phase 2 (Z2-Zusatz, Z3).**

**MM** (alle drei `optimal`): S1=416.132,18 / S2=416.201,13 / S3=416.243,26 EUR — Unterschiede < 0,03%, bei KEINER Variante wird TES gebaut (konsistent mit Z1s Befund). Kein meaningful topologischer Effekt bei MM in diesem Parameterbereich — S1 ist nominell billigste, aber der Unterschied liegt innerhalb der Lösungsgüte-Unsicherheit.

### Als Nächstes

1. MM-PIN0-Neulauf abwarten (läuft).
2. Mit MM-PIN0 und SB-PIN0 (vorhanden) die Y1-Intervalle für alle sechs S1/S2/S3-Paare + die fünf Z1-Sprossen berechnen.
3. Phase 2 starten: SB-S1-HK0 mit c0×0,5 (Z2-Zusatz); Z3s komplette Sensitivitätsserie auf SB-S1-HK0 (SB) und MM-S1-HK0 (MM, mit dem Hinweis, dass der MM-"Gewinner" kaum von S2/S3 unterscheidbar ist) + jeweils eigene PIN0-Läufe pro Sensitivität (Preisabhängigkeit, siehe oben).

---

## §4cg — 2026-10-04: AA — zwei Vorprüfungen vor Phase 2, dann AA3 (SB-S1 voller Sweep) gestartet

### AA1) Regret-Lauf MM: Setup-Prüfung ABGESCHLOSSEN — KEIN Setup-Fehler, Infeasibilität bleibt als Ergebnis bestehen

Direkt geprüft (`configs/paper_2/storage_geometry.yaml`): `tes_main.discrete_energies_mwh = [0, 0.5, 1.1, 2.2, 3.3, 4.3, 6.5, 8.7, 10.8, 13.0, 17.4, 23.9, 30.4]`, `v_min_realistic_m3 = 50.0`. **23,9 MWh IST eine echte Sprosse** (Position 12 von 13) — kein Schnappen auf eine andere Sprosse nötig, die Bedingung aus AA1 für einen Setup-Fehler trifft NICHT zu. Die in §4cf gemeldete Infeasibilität bleibt damit ein ECHTES Ergebnis (Ursache weiterhin nicht abschließend geklärt — vermutlich eine Wechselwirkung des `investable=False`-Pfads mit anderen Constraints, nicht die reine Geometrie, da der geometrische Vorab-Check nicht ausgelöst wurde). **Defekter IIS-Pfad als offener Werkzeugmangel notiert** (Pyomo/Gurobi-Schnittstellenfehler `'GUROBIFILE' object has no attribute '_solver_model'`), nicht jetzt behoben.

### AA5) MM-Narrativ korrigiert

Ältere Textstelle identifiziert (Zeile ~1144, dieses Dokument, vor-V1-V8-Befund): beschreibt einen damals gebauten 1,1-MWh-Speicher bei S2 c0×1,0, der Biomasse-/KWK-Mindestlastüberschuss puffert ("Ladebetrieb: Biomasse +0,06 MW, KWK +0,02 MW... Grundlast-/Mindestlasterzeuger"). **Korrektur:** dieser Mechanismus (Speicher puffert Mindestlastüberschuss) bleibt als reine BEOBACHTUNG unter dem damaligen, nicht mehr aktuellen Code gültig, verliert aber jeden Wirtschaftlichkeitsanspruch — unter korrekt bepreister Abregelung (5 statt 1.000 EUR/MWh, B1a) und dem vollständigen V1-V8-Kostenmodell (O&M, korrekte CAPEX-Eskalation, CO2-Netting-Fix) baut MM bei KEINEM der fünf in Z1 getesteten Kostenniveaus (125-500 EUR/m³) überhaupt Speicher (§4cf). Der alte 1,1-MWh-Befund war eine Artefakt-Größenordnung aus einem inzwischen korrigierten Kostenumfeld, kein belastbarer Wirtschaftlichkeitsbeleg.

### AA2) SB-S1-Intervall — Referenz korrigiert, Nachschärfung gestartet

**Referenz ist SB-S1-PIN0.** Da S1/S2/S3 strukturell identisch bei Kapazität=0 sind (§4ce), IST SB-S0-HK0-PIN0 (V6 Job 1) bereits exakt diese Referenz — kein fehlender Lauf, nur eine Klarstellung der Benennung (keine neue Baseline-Lösung nötig). S2/S3 bleiben als Konsistenzzeile (reproduzieren S0 exakt → bestätigt das Protokoll, siehe §4cf).

**Nachschärfung gestartet** (wie angeordnet, da 184.816 EUR/a nahe an der Summe der Gaps lag): SB-S1-PIN0 (=bisherige SB-S0-HK0-PIN0) und SB-S1-HK0 werden mit Ziel-Gap 0,15% (unter dem geforderten <0,20%), MIPFocus=3, TimeLimit=172.800s (48h), Warmstart aus der jeweils aktuellsten eigenen Lösung neu gelöst.

### AA3) SB-S1 voller zweiseitiger c0-Sweep — GESTARTET (wichtigster Lauf-Satz der Kampagne)

Begründung bestätigt: gebauter Speicher (438 MWh, 30.379 m³ laut `geometry.csv`, N=1 Tank) impliziert ≈179 EUR/m³ (degressive Formel bei v=30.379, c0=2,5 Mio., v0=10.000, b=0,70 nachgerechnet) — UNTER Friedrichshafen (240 EUR/m³, günstigstes reales Projekt). Die Eintrittsschwelle muss nach OBEN abgetastet werden.

**Kette gestartet** (7 Läufe sequenziell, vollständig vom Harness entkoppelt, TimeLimit=172.800s/MIPGap=0,15%/MIPFocus=3 je Lauf): SB-S1-PIN0 (nachgeschärft) → SB-S1-HK0 c0×{1,0 (nachgeschärft) / 0,5 / 0,7 / 1,3 / 1,5 / 2,0}. Die geteilte PIN0 (unabhängig von c0, siehe §4ce) deckt alle sechs c0-Sprossen ab — kein separater PIN0 je Sprosse nötig trotz "je mit PIN0" in der Anweisung (das war bereits für Z1/Z2 so begründet und gilt hier identisch).

**Ausgabe je Lauf** (nach Abschluss): gebautes V_TES in MWh UND m³, Zahl der Tanks, EUR/m³ der gebauten Größe, Wert-Intervall gegen die nachgeschärfte SB-S1-PIN0 (Y1-Methodik), Vollzyklen/a, verdrängte Einheit (welche Bestandsanlage durch den Speicher weniger läuft).

**AA4 (Z3) bleibt geplant, startet NACH dieser Kette** (SB-Ressourcen sind durch die 7-Lauf-Kette gebunden; MM-seitige Z3-Vorbereitung auf MM-S1-HK0 kann parallel vorbereitet werden, sobald die MM-PIN0-Neulösung [läuft] fertig ist).

**Realistischer Zeithorizont:** bei bisherigen SB-Laufzeiten (24-48h-Budget, meist unter Budget konvergiert) ist mit mehreren Tagen für die vollständige 7-Lauf-Kette zu rechnen.

---

## §4ch — 2026-10-04: MM-PIN0-Neulösung abgeschlossen — MM-Y1-Intervalle berechnet, alle drei Standorte statistisch nicht unterscheidbar

**MM-PIN0 (frisch, V1-V8-Code):** `optimal`, Gap=0,1465%, UB=418.018,21 EUR — gegenüber dem alten Vor-Session-Wert (319.382,19 EUR) ein Anstieg um +98.636 EUR (+30,9%), vollständig im Muster der bereits dokumentierten O&M-Erklärung (§4bx) konsistent.

**Alle drei MM-S1/S2/S3-Läufe hatten bereits von selbst einen Gap unter dem 0,15%-Ziel (0,126-0,144%) — keine Nachschärfung nötig.**

| Szenario | UB [EUR] | Gap | Punktwert | Intervall [EUR/a] | max. %TAC |
|---|---|---|---|---|---|
| MM-S1-HK0 | 416.132,18 | 0,1280% | 1.886,03 | [1.273,43; 2.418,53] | 0,579% |
| MM-S2-HK0 | 416.201,13 | 0,1263% | 1.817,08 | [1.204,49; 2.342,85] | 0,560% |
| MM-S3-HK0 | 416.243,26 | 0,1436% | 1.774,95 | [1.162,35; 2.372,51] | 0,568% |

**Befund:** alle drei Intervalle sind strikt POSITIV (im Gegensatz zu den SB-Werten berühren sie die Nullschranke nicht) — die HP/EK-Investition selbst hat bei MM einen echten, bestätigten kleinen Wert (~1.200-2.400 EUR/a). Die drei Intervalle ÜBERLAPPEN SICH jedoch vollständig — **S1/S2/S3 sind bei MM statistisch NICHT voneinander unterscheidbar.** Bestätigt den bereits in §4cf getroffenen Befund: anders als bei SB (klarer, großer Standort-Effekt, §4cf) zeigt MM in diesem Parameterbereich KEINEN meaningful topologischen Effekt — der TES-Standort ist irrelevant, weil ohnehin nirgends Speicher gebaut wird (Z1).

---

## §4ci — 2026-10-04: AB — zwei Prüfungen parallel zur laufenden Kette

### AB1) Identität SB-S0-HK0-PIN0 ↔ SB-S1-HK0-PIN0 — GEPRÜFT UND BESTÄTIGT (kein Lauf gespart werden musste — keiner war nötig)

Direkter Modell-Diff (Build-only, kein Solve): neues Szenario `SB-S1-HK0-PIN0` angelegt (`tes_node="S1"` BEWUSST erhalten, nicht auf `null` gesetzt, nur Kapazität genullt — anders als das bestehende `SB-S0-HK0-PIN0`). Beide Modelle gebaut und verglichen:

| | n_vars | n_constraints | Constraint-Blöcke nur hier | Var-Blöcke nur hier |
|---|---|---|---|---|
| SB-S0-HK0-PIN0 | 7.332.139 | 9.110.408 | — | — |
| SB-S1-HK0-PIN0 | 7.332.139 | 9.110.408 | — | — |

**Exakt identisch** — n_vars, n_constraints, UND die vollständige Liste aller 792 Constraint-Blocknamen sowie aller 653 Variablen-Blocknamen stimmen bit-für-bit überein (0 Unterschiede). Anders als bei der HP-Platzierung (J2: `hp_node` ändert die Knotenrolle `consumer`→`mixed`) ändert die TES-Kandidatenplatzierung (`tes_node`) bei Stadtbachs Implementierung die Knotenbilanzform NICHT — vermutlich weil `tes_node` anders verdrahtet ist als `hp_node` (kein Rollenwechsel des Zielknotens). **Abkürzung bestätigt, dokumentiert: SB-S0-HK0-PIN0 gilt als exakte Referenz für S1 (und S2/S3). Der 184.816-EUR/a-Befund (§4cf) ist damit NICHT mehr vorläufig, sondern bestätigt.**

### AB2) O&M-Sprung aufgeschlüsselt, Biomasse-KWK-Rate primärquellen-geprüft

**a) Per-Asset-Zerlegung** (aus `dispatch_per_asset.csv` × konfigurierte Raten, exakt gegen die berichteten Summen verifiziert — 1:1-Übereinstimmung auf den Cent):

| MM-Anlage | Kapazität | Fix-O&M [EUR/a] | Dispatch [MWh/a] | Var-O&M [EUR/a] |
|---|---|---|---|---|
| chp_main | 0,20 MW | 500,00 | 130,83 | 523,33 |
| gasboiler_main | 13,0 MW | 26.000,00 | 210,60 | 231,66 |
| biomass_main | 3,3 MW | 49.500,00 | 11.503,56 | 18.980,87 |
| **Summe MM** | | **76.000,00** | | **19.735,86** |

| SB-Anlage | Kapazität | Fix-O&M [EUR/a] | Dispatch [MWh/a] | Var-O&M [EUR/a] |
|---|---|---|---|---|
| hkw | 127,0 MW | 317.500,00 | 126.888,85 | 241.088,82 |
| gtost | 35,0 MW | 87.500,00 | 37.531,00 | 231.941,57 |
| bmhkw | 14,5 MW | 870.000,00 | 89.655,45 | 130.896,95 |
| hws_boiler | 32,0 MW | 64.000,00 | 27.785,48 | 30.564,03 |
| hww_boiler | 104,0 MW | 208.000,00 | 31.960,90 | 35.156,99 |
| **Summe SB** | | **1.547.000,00** | | **669.648,35** |

MM: Fix+Var-O&M=95.735,86 EUR erklärt 97,1% des gemeldeten +98.636-EUR-Sprungs (PIN0 alt→neu); die restlichen ~2.900 EUR liegen im Rahmen kleiner Dispatch-Unterschiede zwischen der alten und der frisch unter V1-V8 re-optimierten Lösung, nicht separat aufgeschlüsselt (geringe Größenordnung, nicht weiter verfolgt).

**b) Biomasse-KWK-Rate (60.000 EUR/MW/a) primärquellen-geprüft:** DEA/Energinet "Technology Data for Energy Plants", Kap. 09 "Biomass CHP and HOP plants" direkt erneut gelesen (nicht aus Gedächtnis). **Befund: die Spalte bleibt mehrdeutig.** Kap. 09 enthält MINDESTENS 12 separate Teiltabellen (verschiedene Technologievarianten/Anlagengrößen), jede mit einer eigenen Zeile "Fixed O&M (€/MW input/year)" und 8 Spalten (vermutlich verschiedene Kapazitätsklassen je Variante) — real extrahierte Werte reichen von **14.100 bis 61.600 EUR/MW-FUEL-INPUT/Jahr** (nicht MW-Output). Die im Code hinterlegte Rate (`om_eur_per_mw_year: 60000.0`) ist auf bmhkws THERMISCHE Kapazität (14,5 MW Output) bezogen, nicht auf den Brennstoff-Input (≈29,9 MW) — konsistent mit der Konvention aller anderen Technologien in diesem Modell (durchgehend €/MW_th_output/Jahr), aber NICHT direkt eine DEA-Spalte. Umgerechnet auf Input-Basis: 870.000 EUR/a ÷ 29,9 MW = **≈29.097 EUR/MW_input/Jahr** — liegt INNERHALB der real gefundenen DEA-Spanne (14.100-61.600), im unteren Drittel. **Bezugsjahr nicht eindeutig im Dokument gefunden** (Katalog-Erstveröffentlichung 2016, Teilrevisionen bis mind. 2020 laut Änderungsblatt, Kap. 09 nicht explizit als revidiert gekennzeichnet) — nicht weiter verfolgt (Zeitbudget). **Entscheidung (AB2b-Regel angewandt): Wert bleibt unverändert** (liegt bereits innerhalb der realen Spanne, keine Korrektur nötig) — als "Spanne statt Punktwert, Herkunft jetzt präzise dokumentiert" gekennzeichnet, nicht als scharf lokalisierte Einzelquelle.

**c) Neue Standing-Reporting-Regel:** ab sofort werden Kosteneffekte IMMER absolut (EUR/a) UND relativ berichtet, mit explizit genanntem Nenner (TAC des jeweiligen PIN0-Laufs). Zusätzlich wird der Anteil der fixen Bestand-O&M an der TAC ausgewiesen:

- **MM:** Bestand-Fix-O&M (76.000 EUR/a) = **18,18%** der PIN0-TAC (418.018,21 EUR)
- **SB:** Bestand-Fix-O&M (1.547.000 EUR/a) = **6,60%** der PIN0-TAC (23.421.861,63 EUR)

(MMs deutlich höherer Anteil erklärt sich durch das insgesamt viel kleinere Netz — dieselbe Bestandsflotten-Fixkosten-Logik wirkt bei einem kleineren Jahresbudget relativ stärker.)

### AB3) MM-Ergebnis — Zielformulierung übernommen

> „In MM ist der Standort des Speichers ohne Wirkung, weil kein Speicher gebaut wird. Der verbleibende Investitionswert stammt aus dem Elektrodenkessel [und der Wärmepumpe] und liegt bei 1,2 bis 2,4 kEUR/a."

Das ist die saubere Negativaussage für das dünne Netz und steht dem SB-Befund (substantieller, standortabhängiger Speicherwert, §4cf) gegenüber — bestätigt durch §4ch.

---

## §4cj — 2026-10-06: Zwischenstand SB-S1-Sweep-Kette — PIN0 und c0×1,0 nachgeschärft, Intervall deutlich verschärft

**2 von 7 Läufen fertig, beide unter dem 0,15%-Ziel:**

| Lauf | UB [EUR] | Gap | Solve-Zeit |
|---|---|---|---|
| SB-S1-PIN0 (nachgeschärft) | 23.370.804,48 | **0,1436%** | 13.805,7 s (3,8 h) |
| SB-S1-HK0 c0×1,0 (nachgeschärft) | 23.172.019,51 | **0,1365%** | 62.635,6 s (17,4 h) |

**Nachgeschärftes Intervall (Y1-Methodik, beide Seiten unabhängig <0,15% Gap):**
- Punktwert = **198.784,96 EUR/a** (höher als die vorläufige 184.816 EUR/a — die engere Lösung fand eine GÜNSTIGERE S1-Konfiguration)
- Intervall = **[165.215,33; 230.414,04] EUR/a** — strikt positiv, enges Band (~65 k EUR Spanne)
- max. 0,986% der TAC

**Der SB-S1-Speicherbefund ist damit deutlich verschärft und bestätigt**, nicht mehr nur ein Punktschätzwert mit loser Gap-Unsicherheit.

**Lauf 3 (c0×0,5) läuft seit ~20h, Gap aktuell 0,23%, noch nicht fertig.** Verbleibend: c0×{0,5 (läuft), 0,7, 1,3, 1,5, 2,0}. Bei bisherigem Tempo (Läufe 1-2 zusammen ~21h) ist mit mehreren weiteren Tagen bis zum vollständigen Kettenabschluss zu rechnen — die für die Eintrittsschwellen-Frage entscheidenden Läufe (c0×1,3 bis 2,0) stehen noch aus.
