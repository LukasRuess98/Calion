# REPORT v12 — Bilanzfix + Ergebniskampagne

Antwort auf `docs/paper_2/agent_prompts/v12_Bilanzfix.md` (Fassung v12.3, 2026-11-06). Branch `p2_v9_consolidation`, Basis 7aa6a49.
Dieser Report wird fortlaufend ergänzt. Stand: **Teil 0 abgeschlossen**, Teil A in Arbeit.

---

## 0 — Laufende Läufe

Prüfung aller Paper-2-Prozesse von Lukas am 2026-11-06 ab 15:55 (`Win32_Process`, Kommandozeilen).

| Prozess (Wurzel-PID) | Lauf | Branch / Worktree | Betroffen nach Teil-0-Kriterium? | Maßnahme |
|---|---|---|---|---|
| 95836 `ac_scheduler.py` | Scheduler AC-Block | `Loc_TES_Study_P2` (Haupt-Worktree) | — | weiterlaufen lassen, `PAUSE` gesetzt |
| 70076 `ac_run.sh` → 73544 python | `ac7_c20_k100` SB-S1-HK0 | `Loc_TES_Study_P2` | nein (s. u.) | läuft bis Zeitlimit 86.400 s (Start 05.11. 23:06 → Ende ≈ 06.11. 23:07) |
| 25504 `ac_run.sh` → 62508 bash → 98828 python | `ac7_c20_k000` SB-S1-HK0 | `Loc_TES_Study_P2` | nein (s. u.) | **beendet 16:14:37** (Auftrag 0.3) |

Python-Prozesse mit leerer Kommandozeile und nicht lesbarem Besitzer (Wurzel 55072 u. a., gestartet 04.11. 11:14) gehören nicht zu
Lukas' Konto (`GetOwner` liefert leer) und wurden nicht angefasst. Auf `p2_v9_consolidation` lief kein Solve.

**Begründung „nicht betroffen“ (belegt):**
- `output/_ac/ac7_c20_k100/logs/scenario_runner.log` bzw. `.out`: `Pipe hkw_to_man: max flow = 333.11 kg/s (... bidirectional=False)`.
  Die Umstellung auf bidirektional existiert nur in `p2_v9_consolidation:scripts/paper_2/scenario_runner.py:337-352` („v9 E5“).
- TES an j_hkw (Primärknoten, `Placed tes_sb at node j_hkw (S1)`), WP/EK an j_man ohne Rückflussmöglichkeit.
- `hkw_to_ost` → j_ost ist bidirektional, j_ost hat keine Anlagen (`Stadtbach_topo.yaml:166`, `j_ost: {}`) und fällt nicht in den
  `Q_consumer`-Zweig.
- Die Läufe nutzen den WP-Default-Kanal (Warmstart-Referenz SB-S0: `Q_hp_def_MW` Σ 3.298,6 MWh) und das Investitions-MILP: alter Rahmen,
  kein Rechenfehler. Ergebnisse gehen nicht ins Paper.

**Durchgeführte Schritte:**
1. `output/_ac/PAUSE` angelegt 2026-11-06 16:09 (Inhalt: Begründung v12 Teil 0). Scheduler-Log 16:09:24:
   `PAUSED (output/_ac/PAUSE): no new launch; botRAM=48GB solves=2 pending=8`.
2. `ac7_c20_k100` läuft weiter (Gap zuletzt 0,154 % > Ziel 0,15 %, Schranke stagniert; Ende am Zeitlimit erwartet).
3. `ac7_c20_k000` beendet. Vorher: seit 15:27:14 kein Logeintrag (letzte Zeile: Inkumbent 2,3311e7 = TES-freie Referenz, Schranke 2,3258e7,
   Gap 0,22 %, 14.307 s), CPU-Messung 15:59: 21 CPU-s in 20 s ≈ 1 Kern (k100 im selben Fenster ≈ 15 Kerne).
   `taskkill /T /F /PID 25504` um 16:14:25 → beendet 98828 (python), 62508 (bash), 25504 (bash).
   Nachprüfung 16:14:37: **kein Prozess** mit PID oder Eltern-PID aus {25504, 62508, 98828}. Ausgabe `output/_ac/ac7_c20_k000/` (446 MB)
   nicht gelöscht; Node-File-Verzeichnis leer. Der Scheduler setzt den Job beim nächsten Zyklus selbst auf `failed` (kein `meta.json`,
   `ac_scheduler.py` `main()`), ein Neustart ist ausgeschlossen (nur `queued` wird gestartet, zudem `PAUSE`).
4. `output/_ac/queue.json`: `ac10_k010_resume` und `ac10_s20_resume` von `running` auf `aborted` (mit Notiz). Backup:
   `output/_ac/queue.json.bak_v12_teil0`.
5. Die 8 wartenden Jobs (`ac6_c20_k025_hd2`, `ac7_netz50_c20_k025`, `ac4_ref_netz50`, `ac3_monthly_free_old`, `ac7_c10_k025`,
   `ac7_c15_k025`, `ac6_c20_k025_ep8`, `ac6_c20_k025_ep12`) bleiben `queued` und durch `PAUSE` gesperrt.

Hinweis an die AC-Session: Die drei anderen lokalen Claude-Sessions (`planing-framework-for-heat-84`, `-91`, `-6f`, alle idle) erhielten
16:15 eine Nachricht, dass `PAUSE` und `queue.json` ab jetzt bei der v12-Session liegen und nichts gestartet wird. Welche davon die
AC-Session ist, ist aus der Sitzungsliste nicht ersichtlich.

`output/` ist in `.gitignore` (Zeile 38); Teil 0 ist daher nur hier dokumentiert.

---

## Widersprüche

**W1 — Änderungsliste v12 Punkt 1 vs. E6.** Punkt 1 begründet die Zeitzerlegung damit, ein engeres Ganzjahres-Gap sei „in 8–12 h nicht
erreichbar“. E6 (bindend) macht dagegen den Ganzjahreslauf (Weg A) zum bevorzugten Weg und B9 zum Ausweichweg. Umgesetzt wird E6;
Punkt 1 ist durch die Änderungen v12.1 → v12.2 überholt.

**W2 — „Warmstart je Block aus C0“ (Teil D) bei Weg A.** Weg A hat keine Blöcke. Umsetzung: Warmstart je Lauf aus dem C0-Dump derselben
Netz/HK-Stufe; „je Block“ gilt nur, falls Weg B nötig wird.

---

## Meldepflichten

(noch keine)

---

## A — Diagnose

(in Arbeit)
