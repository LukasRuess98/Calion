# A4 — TES-Geometrie-Formeln (read-only Befund)

## Vorbehalt zum Working-Tree (Pflicht-Check vor Beginn)

Geprüft mit `git log -3 -- calion/models/blocks/geometric_storage.py`,
`git diff HEAD -- calion/models/blocks/geometric_storage.py`,
`git diff HEAD -- calion/models/component_assembler.py` und `git status --short`.

**Befund (abweichend vom Briefing):** Beide Dateien sind zum Zeitpunkt dieser Analyse
**NICHT** als "modified, uncommitted" markiert — `git status --short` ist leer, beide
`git diff HEAD --` sind leer (0 Zeilen). Der aktuelle HEAD-Commit ist `ddae6db`
("Paper 2 AD: withdraw 280,274 EUR/MW …", 2026-10-22), und `geometric_storage.py` /
`component_assembler.py` wurden zuletzt in genau diesem bzw. im vorangehenden
AC-Block-Commit (`812c460`, "Paper 2 AC block: price TES charge/discharge power, 45 m
vessel height cap, run scheduler") verändert — beide sind bereits committed. Es gibt
also **keine separate, parallel-uncommittete Änderungsebene** oberhalb des aktuellen
HEAD; der im Briefing erwähnte AC-Block (Leistungspreise, 45-m-Kappung) ist bereits
vollständig Teil des committeten Codes, den diese Analyse gelesen hat. Dieser Befund
wird unten (a), (c), (e) explizit berücksichtigt, wo er von den analysierten
Alt-Läufen abweicht.

Status: belegt (Evidenz: Bash `git log -3`, `git diff HEAD --`, `git status --short`,
alle am Start dieser Session ausgeführt).

---

### A4a — r_hd: Konstante, Config-Wert oder Solver-Variable? h_max_m: wann aktiv?
Antwort: r_hd ist in BEIDEN Pyomo-Optionen (Option A, Standard, und Option B,
`option_b=True`) ein **exogener Konfigurationswert**, niemals eine vom Solver gewählte
Variable. In Option A wird h_TES nur aus dem gewählten V_TES und dem fixen r_hd
post-solve abgeleitet; in Option B sind h und d zwar echte Pyomo-`Var`, aber die
Beziehung `h == r_hd * d` ist eine harte Gleichheits-Constraint mit konstantem r_hd —
der Solver kann also die Höhe/Volumen-Relation wählen, nicht das Aspect Ratio selbst.
r_hd kommt aus `configs/paper_2/storage_geometry.yaml` (global `r_hd: 2.0` top-level,
oder per-Asset unter `per_asset.<name>.r_hd` — per-Asset gewinnt) und kann zusätzlich
pro Scenario-Run über die Env-Variable `CALION_TES_RHD` als `r_hd_override`
überschrieben werden (scenario_runner.py injiziert dies in die Asset-Config;
component_assembler.py wendet es nach dem YAML-Wert an). Für den analysierten Lauf
SB-S1-HK0 ist r_hd=2.0 (kein Override aktiv).
h_max_m ist ebenfalls ein Config-Wert (`storage_geometry.yaml: h_max_m: 45.0`
top-level, per-Scenario über `CALION_TES_HMAX` überschreibbar). Er ist **inaktiv**
(kein Cap), wenn: der Wert `None`/0/leer ist, ODER die Technologie `pressurized` ist
(`_pressurized=True`), ODER das TES im Scenario deaktiviert ist (`V_max_m3<=0`). Im
analysierten Lauf ist h_max_m in geometry.csv leer → inaktiv; das entspricht dem
Pre-AC2-Codestand (`CALION_TES_HMAX=0`-Äquivalent). Ist h_max_m aktiv, begrenzt es
NICHT die Gesamt-Energie, sondern NUR das Volumen EINES Gefäßes
(`unit_geo_m3 = π·h_max³/(4·r_hd²)`); größere Speicher werden als
N=ceil(V/unit)-identische Gefäße realisiert (Kosten pro Gefäß).
Evidenz: calion/models/blocks/geometric_storage.py:117-134 (Signatur r_hd, h_max_m),
:170-174 (h_max_m-Docstring), :183-184 (`self.h_max_m = float(h_max_m) if h_max_m else None`),
:214-221 (unit_geo_m3-Berechnung); calion/models/component_assembler.py:1325
(`r_hd = float(p.get("r_hd", 3.0))`), :1349-1362 (r_hd_override-Anwendung),
:1354-1355 (h_max_m: `None` wenn falsy/pressurized/disabled); scripts/paper_2/scenario_runner.py:530-537
(`CALION_TES_RHD` → `r_hd_override`, `CALION_TES_HMAX` → `h_max_m`);
configs/paper_2/storage_geometry.yaml:48 (`r_hd: 2.0` top-level, historisch, Stand zum
Zeitpunkt des Alt-Laufs), :61 (`h_max_m: 45.0`, AC2-Zusatz);
output/_s2/sb_c0x05/paper2_runs/SB-S1-HK0/geometry.csv (h_max_m-Feld leer, r_hd=2.0).
Status: belegt
Offen: Im AKTUELLEN (committeten) storage_geometry.yaml steht unter `per_asset.tes_sb`
inzwischen `r_hd: 1.5` (AD5, 2026-10-22, Zeile 234) statt des globalen 2.0 — das ist
eine ECHTE Abweichung vom analysierten Alt-Lauf (nicht nur ein Vorbehalt): ein heute
gestarteter SB-S1-HK0-Lauf würde mit r_hd=1.5 UND h_max_m=45.0 (aktiv) rechnen, nicht
mit r_hd=2.0/h_max_m=None wie der analysierte Lauf. Siehe A4c für die quantitative
Konsequenz (Mehrfach-Gefäße ab AR>~1.7 bei V=30.379 m³).

### A4b — Exakte Formeln: Flächen, Verlust, Kostenkurve
Antwort: **Flächen** (geschlossener Zylinder, V und AR=r_hd=h/d gegeben):
d = (4·V/(π·AR))^(1/3), h = AR·d, Mantel = π·d·h, Boden = Dach = (π/4)·d².
Summe = π·d²·(AR+0.5), was exakt der Code-Funktion `surface_factor(AR)` entspricht:
A_total = k(AR)·V^(2/3) mit k(AR) = π·(AR+0.5)·(4/(π·AR))^(2/3) — algebraisch
äquivalent und numerisch identisch (eigene Rechnung, siehe A4c).
**Verlustformel** (loss_model="surface", aktiv für den Lauf): eine KONSTANTE
(nicht SoC-proportionale) Verlustleistung
Q̇_loss [MW] = u_value_w_m2k · k(AR) · ΔT_loss · V^(2/3) / 1e6, additiv in der
SOC-Dynamik abgezogen (E[t] = E[t-1] + Gewinn − Q̇_loss·dt). ΔT_loss ist dabei
**NICHT** das delta_T_scenario_k (das ist die ENERGIE-ΔT T_hot−T_cold für E_max!),
sondern T_hot−T_amb = (t_return_c + delta_T_scenario_k) − t_amb_c. Für den
analysierten Lauf: 60+15−10 = 65 K (siehe A4c).
Eine separate Funktion `standing_loss_fraction_per_h()` (fraktional, λ=…·V^(-1/3))
existiert im selben Modul, wird aber in `attach()` NICHT aufgerufen — die tatsächlich
im Solve verwendete Verlustformel ist die oben genannte additive Q̇_loss-Variante
inline in `attach()`. `standing_loss_fraction_per_h` scheint ein nicht
mehr genutzter/alternativer Helfer zu sein (nur in geometric_storage.py und im
CHANGELOG referenziert, kein Aufrufer gefunden).
**Kostenkurve** (cost_model="degressive", aktiv für den Lauf):
C = N · c0 · (V/N / v0)^b, ausgewertet PRO GEFÄSS (V/N, N=ceil(V_rung/unit)).
Für den analysierten Lauf: c0=1.250.000 EUR (= 2.500.000 EUR × 0.5, siehe
`CALION_TES_C0_SCALE=0.5` env-Override), v0=10.000 m³, b=0.70. Die Kostenkurve hängt
**NUR vom Volumen** ab (über N und V/N) — **keine zusätzliche AR/Höhen-Korrektur**: im
Code-Pfad (geometric_storage.py:402-414) geht r_hd/h an keiner Stelle in `_cost_k`
ein. Eigene Rechnung (A4c) bestätigt: Kosten und Kosten/m³ sind für AR=1,2,3 exakt
identisch (2.720.918 EUR bzw. 89,56 EUR/m³), solange N (Gefäßanzahl) gleich bleibt.
N selbst kann aber indirekt über AR variieren, wenn h_max_m aktiv ist (A4a/Offen) —
das ist der einzige Mechanismus, über den die Höhe die Kosten beeinflusst (via N, nicht
via eine Formfaktor-Korrektur in C_unit).
Evidenz: calion/models/blocks/geometric_storage.py:58-64 (`surface_factor`),
:67-84 (`standing_loss_fraction_per_h`, unbenutzt), :402-416 (Kostenformel `_cost_k`),
:540-556 (tatsächliche q_loss_mw-Berechnung in `attach()`, inkl. `_dT_loss` Zeile 544);
configs/paper_2/storage_geometry.yaml:112-114 (`c0_eur: 2500000.0`, `v0_m3: 10000.0`,
`exponent_b: 0.70`); output/_s2/sb_c0x05/paper2_runs/SB-S1-HK0/scenario_meta.json
(`c0_eur: 1250000.0`, `c0_scale_env: "0.5"`, `v0_m3: 10000`, `exponent_b: 0.7`,
`u_value_w_m2k: 0.2`, `eta_strat: 0.85`); calion/models/component_assembler.py:1321-1341
(c0/v0/b-Resolution + Authoritative-Check).
Status: belegt (Formeln direkt gelesen) + berechnet (Flächenäquivalenz numerisch
verifiziert, siehe A4c)
Offen: -

### A4c — Offline-Rechnung (V=30.379,4 m³, AR∈{1,2,3})
Antwort: Mit den unter A4b belegten Formeln, den echten Lauf-Parametern
(delta_T_scenario_k=15,0 K für E_max; t_return_c=60,0 °C, t_amb_c=10,0 °C →
ΔT_loss=65,0 K für den Stillstandsverlust; u_value_w_m2k=0,20; c0=1.250.000 EUR,
v0=10.000 m³, b=0,70; N=1 Gefäß, da h_max_m im Lauf inaktiv war und V<unit_tank_m3=
50.000 m³) ergibt sich (volle Tabelle in der CSV-Datei):

| AR (r_hd) | h [m] | d [m] | Gesamtfläche [m²] | Verlust [MWh/a] | Kosten [EUR] | EUR/m³ |
|---|---|---|---|---|---|---|
| 1.0 | 33,82 | 33,82 | 5389,7 | 613,78 | 2.720.918 | 89,56 |
| 2.0 | 53,68 | 26,84 | 5658,9 | 644,43 | 2.720.918 | 89,56 |
| 3.0 | 70,35 | 23,45 | 6045,9 | 688,51 | 2.720.918 | 89,56 |

**Validierung AR=2.0 gegen echten Lauf:** eigene Formel liefert h=53,6846 m
(gerundet 53,68 m) — stimmt mit dem echten `geometry.csv`-Wert h_TES_m=53,68 m exakt
überein (Differenz <0,005 m, reine Rundung). Zusätzliche Kreuz-Validierung (nicht
gefordert, aber bestätigend): die daraus abgeleitete p_betr-Formel (A4d) liefert bei
h=53,6846 m exakt 6,131 bar — identisch mit dem echten Lauf-Wert p_betr_bar=6,131.
Auch E_max = energy_coeff·V = 438,00 MWh (energy_coeff aus eta_strat/rho/cp/delta_T)
und cap_power = 0,25·E_max = 109,50 MW reproduzieren die echten Lauf-Werte exakt.
Vier unabhängige Größen (h, p_betr, E_max, cap_power) stimmen exakt — starke
Bestätigung, dass die gefundenen Formeln die tatsächlich im Solve verwendeten sind.
Hinweis zur Literatur-Plausibilität (nur Vergleich, keine Modellquelle): Reuter West
hat bei ~56.000 m³ eine Höhe von ~45 m (AR≈1,05). Der analysierte Lauf (AR=2,0,
V=30.379 m³, deutlich kleineres Volumen) liegt mit h=53,68 m bereits ÜBER der
Reuter-West-Höhe, obwohl das Volumen nur gut die Hälfte beträgt — das ist genau der
in storage_geometry.yaml:53-59 dokumentierte Befund, der zur Einführung des
AC2-Höhenlimits h_max_m=45 geführt hat.
Evidenz: eigene Python-Rechnung (Taschenrechner-Arithmetik mit den A4b-Formeln,
Konstanten aus calion/constants.py: RHO_WATER_HOT_KG_M3=971.8, CP_WATER_HOT_KJ_PER_KGK=4.189,
G_ACCEL_M_S2=9.81, P_ATM_BAR=1.013); Validierungs-Soll-Werte aus
output/_s2/sb_c0x05/paper2_runs/SB-S1-HK0/geometry.csv
(h_TES_m=53.68, p_betr_bar=6.131, E_TES_max_MWh=438.0, cap_power_MW=109.5); volle
Tabelle inkl. Mantel/Boden/Dach-Einzelflächen in
docs/paper_2/agent_reports/tables/A4_geometry_offline_calc.csv.
Status: berechnet (Formeln belegt, Zahlen selbst gerechnet, gegen 4 echte
Lauf-Werte validiert)
Offen: Unter dem AKTUELLEN (committeten) Code/Config (r_hd_tes_sb=1.5, h_max_m=45.0
aktiv) wäre das Ergebnis anders: unit_geo_m3 bei h_max=45m ist π·45³/(4·AR²) — für
AR=1,5 ergibt das 31.809 m³ (> V=30.379 m³ → noch N=1 möglich), für AR=2,0 nur
17.892 m³ (< V → N=2 Gefäße nötig), für AR=3,0 nur 7.952 m³ (→ N=4). Das wurde NICHT
in die Haupttabelle übernommen (die Aufgabe fragt nach den Formeln des analysierten
Alt-Laufs), ist aber als Kontext-Rechnung in den Skript-Notizen vorhanden und hier
dokumentiert, weil es die vom Briefing verlangte "nur wenn der aktuelle Code
abweicht"-Erklärung ist.

### A4d — p_betr_bar=6,131 vs. p_design_bar=5,5: Widerspruch?
Antwort: Kein Widerspruch — es sind zwei verschiedene Größen, und das Modell nutzt
p_max_bar für diesen (atmosphärischen) Tank-Typ NICHT als harte Volumen-Schranke.
p_betr_bar ist der **tatsächliche hydrostatische Betriebsdruck am Tankboden** aus der
real realisierten Höhe: p_betr = p_atm + ρ·g·h/1e5 (h=53,68 m → 6,131 bar). p_design_bar
(=p_max_bar=5,5 bar, aus storage_geometry.yaml) ist dagegen ein **dokumentierter
Referenzwert** für eine andere Tankklasse (druckbeaufschlagtes Gefäß, Study-G/legacy),
der nur für `tes_technology: pressurized` die Volumengrenze strukturell bestimmt
(`pressure_limits_size=True`). Für die atmosphärische (Standard-)Technologie, die
dieser Lauf nutzt, übergibt component_assembler.py explizit
`pressure_limits_size=_pressurized` = False, sodass p_max_bar NICHT in die
Volumen-/Höhenbegrenzung (V_max_effective) einfließt — der Code-Kommentar begründet
dies damit, dass ein atmosphärischer, flachbödiger EN14015/API650-Tank konstruktiv
KEIN Druckgefäß ist: seine Wand wird über Umfangsspannung (hoop stress) für genau die
hydrostatische Last ausgelegt, die seine tatsächliche Höhe erzeugt — es gibt also
keinen festen "Auslegungsdruck", der die Höhe begrenzen würde. p_betr_bar > p_design_bar
ist in diesem Modell daher lediglich ein Hinweis, dass der real gebaute Tank höher
ist als der für die druckbeaufschlagte Referenzklasse dokumentierte Wert — keine
Modellinkonsistenz, aber (siehe A4c) genau der Befund, der im selben Changelog
(storage_geometry.yaml:53-59) zur AC2-Einführung von h_max_m=45 geführt hat, um
dieses Ergebnis real zu begrenzen.
Evidenz: calion/models/blocks/geometric_storage.py:18-20 (Docstring `p_betr = p_atm +
rho*g*h_TES/1e5 ≤ p_max`), :160-164 (`pressure_limits_size`-Flag-Doku),
:252-266 (V_max_effective-Logik, nur bei `pressure_limits_size=True` greift
p_max_bar); calion/models/component_assembler.py:1457-1460
(`pressure_limits_size=_pressurized` beim Blockaufruf); scripts/paper_2/extract_artefacts_p2.py:146-150
(exakte p_betr-Berechnung für geometry.csv: `p_betr = _P_ATM + _RHO*_G*h/1e5`);
calion/utils/heizkurve.py:147-162 (gleiche Formel, zweite Implementierung/Hilfsfunktion
`tes_operating_pressure_bar`); configs/paper_2/storage_geometry.yaml:53-59
(Kommentar zum h=53,68m/6,131bar-Befund und dessen Überschreiten von
p_max_bar=5,5bar≙47,1m sowie der Reuter-West-Präzedenz).
Status: belegt
Offen: -

### A4e — Formel für cap_power_MW: was begrenzt sie strukturell?
Antwort: Im analysierten Lauf (power_to_energy_ratio nicht gesetzt →
`default_ratio=0.25`) ist cap_power eine Pyomo-Var mit oberer Schranke
`V_max_effective·energy_coeff·0,25·2` und der Constraint `cap_power ≤ 0,25·E_max_expr`
— strukturell also eine **feste E/P-Ratio** (4-Stunden-Entladezeit), NICHT durch
Rohrleitungs-/Hydraulik-Grenzen begrenzt, und (in diesem Lauf) **kostenlos**
(power_capex_eur_per_mw=0,0, siehe geometry.csv). Rechnerisch: 0,25·438,0 MWh =
109,5 MW — exakt der echte Lauf-Wert cap_power_MW=109,5.
Evidenz: calion/models/blocks/geometric_storage.py:423-453 (power_to_energy_ratio-Pfad
und default_ratio=0.25-Pfad), :612-613 (`Qc[t]<=cap_p`, `Qd[t]<=cap_p`), :648-649
(Shared-Port-Constraint `Qc+Qd<=cap_p`); output/_s2/sb_c0x05/paper2_runs/SB-S1-HK0/geometry.csv
(cap_power_MW=109.5, p2e_ratio=0.25, power_capex_eur_per_mw=0.0).
Status: belegt + berechnet (0,25×438,0=109,5 exakt reproduziert)
Offen: Im AKTUELLEN (committeten) Code/Config ist das strukturell anders (echte
Abweichung, nicht nur Vorbehalt): `storage_geometry.yaml` per_asset.tes_sb setzt
inzwischen `power_to_energy_ratio: 1.0` UND `power_max_mw: 120.0` (AD2, Zeilen 236-239)
sowie global `power_capex_eur_per_mw: 22100.0` (Zeile 103). cap_power ist dann eine vom
Solver FREI GEWÄHLTE, über power_capex_eur_per_mw PREISLICH BESTRAFTE Variable, deren
obere Schranke der KLEINERE von (a) E/P-Bound 1,0·E_max und (b) dem hydraulischen Cap
power_max_mw=120 MW ist (letzterer aus einer DN600-Leitung bei v_max=3 m/s, ΔT=35K
hergeleitet, siehe storage_geometry.yaml:235-239-Kommentar: 971,8 kg/m³·3 m/s·0,2827 m²·
4,19 kJ/kgK·35 K ≈ 120,9 MW). Das ist eine inhaltliche Modell-Änderung gegenüber dem
analysierten Alt-Lauf, nicht nur eine Konfigurationsnuance.

---

## Zusammenfassung

Alle fünf Teilfragen sind mit direkter Code-/Config-/Lauf-Evidenz beantwortet und für
den geometrischen Kern (Flächen-, Verlust- und Höhenformel) zusätzlich durch eine
eigene Taschenrechner-Rechnung validiert, die bei AR=2,0 vier unabhängige Größen
(h_TES_m, p_betr_bar, E_TES_max_MWh, cap_power_MW) exakt gegen den echten Lauf
SB-S1-HK0 reproduziert — die identifizierten Formeln sind mit sehr hoher Sicherheit
die tatsächlich im Solve verwendeten.

Kernbefunde:
1. r_hd ist immer ein exogener Config-Wert (nie eine Solver-Variable), überschreibbar
   per Scenario über `CALION_TES_RHD`/`r_hd_override`. h_max_m ist ebenfalls
   Config/Env-gesteuert und war im analysierten Lauf inaktiv (None).
2. Flächenformeln (Mantel/Boden/Dach) sind exakt algebraisch äquivalent zur
   Code-Funktion `surface_factor(AR)·V^(2/3)`. Die Verlustformel nutzt eine ANDERE
   ΔT (T_hot−T_amb=65K) als die Energie-Kapazitätsformel (delta_T_scenario_k=15K,
   T_hot−T_cold) — eine Verwechslungsgefahr, die im Briefing selbst schon knapp
   angelegt war und hier explizit aufgelöst wurde.
3. Die degressive Kostenkurve hängt NUR vom Volumen (bzw. Volumen/Gefäß) ab, nicht
   von AR/Höhe direkt — AR beeinflusst Kosten nur indirekt über die Gefäßanzahl N,
   wenn ein Höhenlimit aktiv ist.
4. p_betr_bar (hydrostatischer Betriebsdruck) und p_design_bar (dokumentierter
   Referenzwert für die druckbeaufschlagte Variante) sind für die atmosphärische
   Technologie strukturell entkoppelt (`pressure_limits_size=False`) — kein Bug,
   sondern Absicht (EN14015/API650-Begründung im Code).
5. cap_power folgte im analysierten Lauf einer festen, kostenlosen E/P-Ratio
   (0,25 = 4h); im AKTUELLEN committeten Code (AC1/AC2/AD2, bereits Teil von HEAD,
   nicht uncommitted) ist Leistung eine bepreiste, hydraulisch gedeckelte
   Entscheidungsvariable — eine echte inhaltliche Abweichung vom analysierten
   Alt-Lauf, nicht nur eine Formulierungsnuance.

Wichtigster Vorbehalt: Der Working-Tree-Hinweis aus dem Auftrag ("aktuell als
modified, uncommitted markiert") traf zum Zeitpunkt dieser Analyse NICHT zu — beide
betroffenen Dateien waren clean und auf HEAD (`ddae6db`). Die oben unter "Offen"
vermerkten Abweichungen zwischen dem analysierten Alt-Lauf und dem "aktuellen Code"
sind daher Abweichungen gegenüber bereits COMMITTETEM Code, nicht gegenüber einer
parallelen uncommitted Session.
