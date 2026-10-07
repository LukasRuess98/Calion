# -*- coding: utf-8 -*-
"""Baut AUTOREN_REFERENZ.md aus einem outputs/<run_ts>/-Ordner: eine einzige
Übersicht mit allen Abbildungen (Pfad + Bildunterschriftsvorschlag), allen
Tabellen (voller Inhalt) und allen Kernzahlen (nach Draft-Abschnitt sortiert,
mit Marker, Wert und Rückverfolgbarkeit), damit der Draft manuell befüllt
werden kann, ohne einzelne CSVs/JSONs durchsuchen zu müssen.

Aufruf: python build_author_reference.py [run_ts]
Ohne Argument wird der neueste Ordner unter outputs/ verwendet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent


def latest_run_dir() -> Path:
    runs = sorted((BASE_DIR / "outputs").iterdir(), key=lambda p: p.name)
    return runs[-1]


def load_run(run_ts: str | None) -> Path:
    if run_ts:
        d = BASE_DIR / "outputs" / run_ts
    else:
        d = latest_run_dir()
    if not d.exists():
        raise SystemExit(f"Run-Ordner nicht gefunden: {d}")
    return d


FIGURES = [
    ("Abb. 1", "fig01_superstructure",
     "Systemgrenze / Superstruktur: Grundlast + Wärmepumpe + Elektrodenkessel + Gaskessel "
     "speisen (über Wärmespeicher) ein Prozesswärme-Band; Netzentgelt gilt für den "
     "GESAMTNETZBEZUG (G-04). Statische Abbildung, kein Datenbezug.",
     None),
    ("Abb. 2", "fig02_analytics",
     "(a) sigma_NEV(h) vs. sigma_AgNes(h) für Ebene MS, log-x, mit h*-Marker: zeigt den "
     "nach oben unbeschränkten Aufschlag unter StromNEV gegenüber dem auf AP2-AP1 "
     "gedeckelten Aufschlag unter AgNes. (b) theta(alpha,f)-Heatmap mit der Isolinie "
     "theta=1 -- zeigt die in R-01 belegte Spannweite (Faktor 8,75).",
     ["fig02_analytics_sigma.csv", "fig02_analytics_theta.csv"]),
    ("Abb. 3", "fig03_core_results",
     "(a) Inkrementelle Wärmekosten (LCOH^inc) je Standort über die vier Regime "
     "00/01/10/11. (b) Anlagenauslegung (HP/EK/GB, gestapelt) unter AgNes/Day-Ahead. "
     "(c) Wärmespeicherkapazität je Standort (ein Band) unter AgNes/Day-Ahead.",
     ["fig03a_lcoh.csv", "fig03_core_results.csv"]),
    ("Abb. 4", "fig04_load_duration",
     "Jahresdauerlinien je Standort (ELEC, AgNes, Day-Ahead) mit bestellter Kapazität C, "
     "realisiertem P_max, der E2-Fläche (Bezug oberhalb C) und h*-Marker auf der "
     "Dauerachse -- zentrale Abbildung für den Bestellregel-Befund (§6.4).",
     ["fig04_load_duration.csv"]),
    ("Abb. 5", "fig05_breakeven",
     "Fossiler Break-even-Gaspreis und -CO2-Preis je Standort UND Netzregime "
     "(ELEC vs. GAS, Day-Ahead-Beschaffung, ELEC-Kapazitäten aus dem jeweiligen "
     "S1-Optimum im Redispatch-Modus).",
     ["breakeven.csv", "breakeven_shift.csv"]),
]

TABLES = [
    ("Tab. 1", "table01_regulatory", "Modellrelevanter Regimevergleich StromNEV vs. AgNes mit Fundstellen."),
    ("Tab. 2", "table02_cases", "Standortübersicht (Wärmebedarf, Volllaststunden, Grundlast, Ebene, P_grid, P_max_prev)."),
    ("Tab. 3", "table03_core_results", "Kern-KPI je Standort (LCOH_inc, Delta_Netz, Delta_Preis, Delta_inter, C/P_max, E2/E)."),
]

# Marker -> (Draft-Abschnitt, Kurzbeschreibung). Reihenfolge = Reihenfolge im Draft.
SECTION_MAP: list[tuple[str, list[str]]] = [
    ("Titel/Fußnote 1", ["REG-01"]),
    ("Abstract DE/EN", ["R-ABS-01", "R-ABS-02", "R-ABS-03"]),
    ("Kernaussagen (ZWF-Kasten)", ["R-CORE-01", "R-INT-01"]),
    ("§2 AgNes vs. StromNEV / Tab.1", ["REG-02", "REG-03", "REG-04"]),
    ("§3.3 Dimensionslose Form theta", ["R-01"]),
    ("§5 Fallstudien / Tab.2", []),
    ("§6.1 Datenqualität und Validierung", ["R-VAL-01", "R-VAL-02", "R-VAL-03", "R-VAL-04",
                                            "R-TIME-01", "R-TIME-02"]),
    ("§6.2 Kostenwirkung und Interaktion", ["R-NET-FIX-MIN", "R-NET-FIX-MAX", "R-NET-DA-MIN",
                                            "R-NET-DA-MAX", "R-INT-NEG-N", "R-INT-MIN", "R-INT-MAX",
                                            "R-DEC-MECH", "R-DEC-DISP", "R-DEC-DESIGN"]),
    ("§6.3 Auslegung", ["R-DES-HP", "R-DES-EK", "R-DES-EF", "R-TES-MIN", "R-TES-MAX",
                        "R-TES-VALUE", "R-TES-CASE"]),
    ("§6.4 Bestellkapazität und Regelgüte", ["R-BOOK-MIN", "R-BOOK-MAX", "R-E2", "V-01", "V-04",
                                             "R-RULE-DEV", "R-RULE-DIR"]),
    ("§6.5 Fossiler Break-even", ["R-BE-GAS", "R-BE-CO2", "R-BE-SHIFT"]),
    ("§6.6 Tarifsensitivität / Tab.3", ["R-SENS-C", "R-SENS-TES", "R-SENS-THETA", "V-02"]),
    ("§7.4 Grenzen (Perfect Foresight vs. Rolling Horizon)", ["V-03"]),
    ("§8 Fazit", ["R-CONCLUSION-01", "R-CONCLUSION-02"]),
    ("Literatur", ["BIB-01", "BIB-02", "BIB-03"]),
]


import re

_RANGE_RE = re.compile(r"(-?[\d.,]+)\.\.(-?[\d.,]+)")


def md_escape(s: str) -> str:
    s = str(s).replace("|", "\\|").replace("\n", " ")
    # ".."-Range-Trenner ist bei negativen Zahlen mehrdeutig (z.B. "-21.374..11")
    # -> in "von X bis Y" umschreiben (rein kosmetisch, kein Wertwechsel).
    s = _RANGE_RE.sub(r"von \1 bis \2", s)
    return s


def build(run_dir: Path) -> str:
    values = json.loads((run_dir / "paper_values.json").read_text(encoding="utf-8"))
    open_df = pd.read_csv(run_dir / "open_markers.csv") if (run_dir / "open_markers.csv").exists() else pd.DataFrame(columns=["marker", "begruendung"])
    open_map = dict(zip(open_df["marker"], open_df["begruendung"]))

    lines: list[str] = []
    lines.append("# Autoren-Referenz — agnes_p2h")
    lines.append("")
    lines.append(f"Automatisch erzeugt aus `outputs/{run_dir.name}/`. Diese Datei sammelt alles, "
                 "was gebraucht wird, um den Paper-Draft manuell (oder per Skript, s. bereits "
                 "erzeugtes `draft_filled.md` im selben Ordner) mit Abbildungen, Tabellen und "
                 "Ergebnissen zu befüllen.")
    lines.append("")
    lines.append(f"**Belegte Marker:** {len(values)}  **Offene Marker:** {len(open_map)}  "
                 f"**Quellordner:** `outputs/{run_dir.name}/`")
    lines.append("")

    # --- Abbildungen ---------------------------------------------------
    lines.append("## 1. Abbildungen")
    lines.append("")
    for num, base, caption, data_csvs in FIGURES:
        lines.append(f"### {num} — `{base}`")
        lines.append("")
        lines.append(f"- **Datei:** `figures/{base}.pdf` / `figures/{base}.png`")
        if data_csvs:
            lines.append(f"- **Quelldaten:** {', '.join(f'`{c}`' for c in data_csvs)}")
        lines.append(f"- **Bildunterschrift-Vorschlag:** {caption}")
        lines.append("")

    # --- Tabellen --------------------------------------------------------
    lines.append("## 2. Tabellen")
    lines.append("")
    for num, base, desc in TABLES:
        lines.append(f"### {num} — {desc}")
        lines.append("")
        md_path = run_dir / f"{base}.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            content = "\n".join(content.splitlines()[2:])  # H1 aus Datei entfernen (Titel oben gesetzt)
            lines.append(content)
        else:
            lines.append(f"*(Datei {base}.md nicht gefunden)*")
        lines.append("")
        lines.append(f"Rohdaten: `tables/{base}.csv`")
        lines.append("")

    # --- Supplement ------------------------------------------------------
    supp_dir = run_dir / "tables"
    if supp_dir.exists():
        supp_files = sorted(p.name for p in supp_dir.glob("supplement_*.csv"))
        if supp_files:
            lines.append("### Supplement (vollständige Sweep-/Testergebnisse)")
            lines.append("")
            for f in supp_files:
                lines.append(f"- `tables/{f}`")
            lines.append("")

    # --- Kernzahlen nach Draft-Abschnitt ----------------------------------
    lines.append("## 3. Kernzahlen nach Draft-Abschnitt")
    lines.append("")
    lines.append("Jede Zeile: Marker im Draft (`[[MARKER]]`) -> Wert -> woher (KPI/Datei).")
    lines.append("")
    seen = set()
    for section, markers in SECTION_MAP:
        real_markers = [m for m in markers if m in values or m in open_map]
        if not real_markers:
            continue
        lines.append(f"### {section}")
        lines.append("")
        lines.append("| Marker | Wert | Quelle |")
        lines.append("|---|---|---|")
        for m in real_markers:
            seen.add(m)
            if m in values:
                v = values[m]
                lines.append(f"| `{m}` | {md_escape(v['display_value'])} | `{v['result_file']}` |")
            else:
                lines.append(f"| `{m}` | **OFFEN** — {md_escape(open_map[m])} | — |")
        lines.append("")

    # --- Restliche Marker (nicht in der Section-Map erfasst) --------------
    remaining = [m for m in values if m not in seen]
    if remaining:
        lines.append("### Sonstige belegte Marker (nicht in einem Abschnitt oben verortet)")
        lines.append("")
        lines.append("| Marker | Wert | Quelle |")
        lines.append("|---|---|---|")
        for m in sorted(remaining):
            v = values[m]
            lines.append(f"| `{m}` | {md_escape(v['display_value'])} | `{v['result_file']}` |")
        lines.append("")

    # --- Offene Punkte -----------------------------------------------------
    lines.append("## 4. Noch offene Punkte (manuell zu klären)")
    lines.append("")
    if len(open_map):
        for m, reason in open_map.items():
            lines.append(f"- **`{m}`**: {reason}")
    else:
        lines.append("Keine offenen Marker.")
    lines.append("")

    lines.append("## 5. Weitere Dateien im Run-Ordner")
    lines.append("")
    lines.append("- `draft_filled.md` — der komplette Draft mit automatisch eingesetzten Werten "
                 "(Ausgangspunkt für die manuelle Überarbeitung)")
    lines.append("- `open_issues.md` — methodische Abweichungen, unverified-Parameter-Liste")
    lines.append("- `qa_report.md` — Selbsttest- und Solver-Diagnostik-Zusammenfassung")
    lines.append("- `environment.md` — Run-ID, Config-Hash, Softwareversionen (für Reproduzierbarkeit)")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    run_ts = sys.argv[1] if len(sys.argv) > 1 else None
    run_dir = load_run(run_ts)
    out_text = build(run_dir)
    out_path = BASE_DIR / "AUTOREN_REFERENZ.md"
    out_path.write_text(out_text, encoding="utf-8")
    print(f"Geschrieben: {out_path} (aus {run_dir})")
