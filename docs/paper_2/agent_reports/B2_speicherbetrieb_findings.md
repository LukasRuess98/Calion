# B2 — Speicherbetrieb SB-S1 (c0×1,0) und SPREIZ20

Datengrundlage: `dispatch_hourly.csv` (8.760h) für `output/v7_final/SB-S1-HK0` und
`output/_z3b/sb_free_spreiz20/paper2_runs/SB-S1-HK0-SPREIZ20`, ausgewertet via
`docs/paper_2/agent_reports/scripts/build_b2_speicherbetrieb.py`. Ergebnisse in
`tables/B2_speicherbetrieb_summary.csv` (Kennzahlen) und `tables/B2_speicherbetrieb_monatsprofil.csv` (12 Zeilen/Lauf).

## Kennzahlen (belegt/berechnet aus dispatch_hourly.csv)

| Kennzahl | c0×1,0 | SPREIZ20 |
|---|---|---|
| Vollzyklen/a (Entladung/E_TES_max=438 MWh) | 69,9 | 89,3 |
| Ladung [MWh/a] | 32.556,7 | 41.524,5 |
| Entladung [MWh/a] | 30.635,9 | 39.114,2 |
| Implizierter Netto-Verlust [MWh/a] (= Ladung − Entladung − ΔSOC_Jahr) | 1.920,7 | 2.410,2 |
| SOC P5/P50/P95 [MWh] | 23,7 / 232,1 / 437,3 | 30,6 / 251,7 / 583,8* |
| Ladestunden / Entladestunden | 1.561 / 2.289 | 1.535 / 2.407 |
| Stunden an Leistungsgrenze (Laden, 109,5 MW) | 125 | 146 |
| Stunden an Leistungsgrenze (Entladen) | 0 | 0 |

Status: belegt (Rohwerte direkt aus CSV), berechnet (Vollzyklen, Verlust, Perzentile).
*SPREIZ20s P95 (583,8 MWh) > E_TES_max=438 MWh der c0×1,0-Referenzgeometrie — NACHTRÄGLICH VERIFIZIERT: SPREIZ20 baut
tatsächlich einen GRÖSSEREN Tank, `output/_z3b/sb_free_spreiz20/paper2_runs/SB-S1-HK0-SPREIZ20/geometry.csv` zeigt
`E_TES_max_MWh=585,0` (V=40.575,2 m³, cap_power=146,25 MW) — die 69,9/89,3 Vollzyklen-Angabe oben nutzt fälschlich
den FALSCHEN (c0×1,0-)Nenner 438 MWh für SPREIZ20; korrigiert: Vollzyklen SPREIZ20 = 39.114,2/585,0 = **66,9**
(statt 89,3). Höhere Preisspreizung führt also zu einem GRÖSSEREN Speicher, nicht zu mehr Vollzyklen auf
gleicher Basis. Status: belegt (korrigiert).

## Mechanismus (berechnet, Korrelationsanalyse)

Pearson-Korrelation Ladeleistung vs. Strom-Bezugspreis (`lambda_buy_eur_MWh`): **+0,305** (c0×1,0) / **+0,334**
(SPREIZ20) — SCHWACH POSITIV, nicht negativ. Reine Preis-Arbitrage ("billig laden, teuer entladen") würde eine
NEGATIVE Korrelation zwischen Ladeleistung und Bezugspreis erwarten lassen — das Vorzeichen spricht GEGEN
Preisarbitrage als Hauptmechanismus.
Pearson-Korrelation Ladeleistung vs. KWK-Wärmeleistung (`Q_chp_MW`): **+0,604** (c0×1,0) / **+0,670** (SPREIZ20) —
DEUTLICH POSITIV. Das spricht für **KWK-Stromführung/Baseload-Glättung**: der Speicher wird vorrangig geladen, wenn
die KWK-Anlage ohnehin hoch fährt, statt bei niedrigem Strompreis.
Status: berechnet (einfache Pearson-r, keine kausale Analyse)

**Bestätigung über Betriebsstunden der Bestandsanlagen (PIN0 vs. S1, vorher/nachher):**

| Anlage | PIN0: Stunden>0 / Energie [MWh/a] | S1: Stunden>0 / Energie [MWh/a] | Δ Stunden | Δ Energie |
|---|---|---|---|---|
| Gasboiler | 2.316 / 59.245,8 | 1.576 / 45.299,1 | **−740 (−32%)** | **−13.946,7 (−23,5%)** |
| EK | 1.062 / 5.309,2 | 736 / 3.902,5 | **−326 (−31%)** | **−1.406,7 (−26,5%)** |
| Biomasse | 8.760 / 432.181,5 | 8.760 / 435.897,1 | 0 | +3.715,6 (+0,9%) |
| KWK (CHP) | 3.633 / 164.219,0 | 2.915 / 168.888,3 | **−718 (−20%)** | **+4.669,3 (+2,8%)** |

Evidenz: `output/v7_final/{SB-S0-HK0-PIN0,SB-S1-HK0}/dispatch_hourly.csv` (Spalten `Q_gasboiler_MW`, `Q_ek_MW`,
`Q_biomass_MW`, `Q_chp_MW`).
Status: belegt

**Fazit (berechnet):** Die TES-Investition verdrängt primär den **Gasboiler** (−32% Betriebsstunden, −23,5% Energie)
und in geringerem Maß die **EK** (−31%/−26,5%) — beide sind teure Spitzenlast-/Backup-Erzeuger. Die **KWK läuft
seltener, aber mit höherer mittlerer Auslastung** (−20% Stunden, aber +2,8% Energie = weniger
Teillast-Zyklen, mehr Volllast) — der Speicher glättet die KWK-Fahrweise, statt sie zu ersetzen. Das stützt die
Korrelationsanalyse: Mechanismus ist **KWK-Baseload-Glättung + Verdrängung von Gasboiler/EK-Spitzenlast**, NICHT
primär Strompreis-Arbitrage.

## Entlademaske — Diskrepanz (Meldepflicht)

Bekannt aus Logzeile (`output/.../chain.output`): `"tes_sb: discharge mask ON (ceiling 95°C, tech property) ->
2025/8760 h blocked (T_VL>ceiling)"` → **2.025 Stunden** blockiert (belegt, Log-Zitat).
Meine eigene Nachrechnung (`T_supply_C > 95.0` in `dispatch_hourly.csv`) ergibt **6.552 Stunden** — ein KOMPLETT
ANDERER Wert. Das deutet darauf hin, dass `T_supply_C` in `dispatch_hourly.csv` NICHT dieselbe Temperatur ist, die
die Entlademaske tatsächlich gegen die 95°C-Decke prüft (vermutlich eine andere Referenzstelle: Netzmittel-/
Erzeuger-T_VL vor Knotenabfall vs. die hier exportierte — evtl. bereits abgesenkte oder andere — Größe).
Status: belegt (beide Zahlen real, aber widersprüchlich) / vermutet (Ursache der Diskrepanz)
**Meldepflicht B2-M1:** Ungeklärte Diskrepanz zwischen der im Solver-Log berichteten Maskierungs-Stundenzahl (2.025h)
und einer Nachrechnung aus dem Export (6.552h, Faktor 3,2×). Nicht aufgelöst — würde eine gezielte Prüfung des
Maskierungs-Codes (`calion/models/blocks/geometric_storage.py`, discharge mask block) gegen die exportierte
`T_supply_C`-Spalte benötigen. Aufwand: klein-mittel.

## Offene Punkte
- **Lade-/Entlademenge "je Erzeuger"** (wie im Auftrag gefordert) ist aus `dispatch_hourly.csv` NICHT direkt
  ablesbar — die Spalte `Q_storage_charge_MW` ist ein einzelner Aggregatwert, keine Quelle-für-Quelle-Aufschlüsselung.
  Die Korrelationsanalyse (oben) ist eine Annäherung, kein Ersatz für eine echte Zuordnung. Eine genaue Zuordnung
  bräuchte entweder eine Energiebilanz-Gleichung pro Zeitschritt (aus dem Pyomo-Modell, kein neuer Solve nötig, nur
  ein Read der Constraint-Struktur) oder eine Zusatz-Exportspalte, die aktuell nicht existiert.
- SPREIZ20s eigene TES-Geometrie (vermutlich größer als 438 MWh, siehe P95-Hinweis oben) wurde nicht gegen ihre
  eigene `geometry.csv` verifiziert — sollte vor Veröffentlichung der Monatsprofile nachgeholt werden.
