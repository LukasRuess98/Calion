"""Pre-commit scan for real names (anonymisation rule). Reads the term lists from local, gitignored files only.

    python -m scripts.dhn_study.central_tes.name_scan <files...>     # exit code 1 on any hit
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

from .. import daten


def terms() -> list[str]:
    r = daten.repo_root()
    an = r / "data" / "raw_dhn_a" / "anonymisierung"
    out: set[str] = set()
    if (an / "klar_phrasen.json").exists():
        out |= {t for t in json.loads((an / "klar_phrasen.json").read_text(encoding="utf-8")) if len(t) >= 4}
    if (an / "zuordnung_verbraucher.csv").exists():
        out |= set(pd.read_csv(an / "zuordnung_verbraucher.csv")["klarname"].dropna().astype(str))
    loc = r / "configs" / "local" / "central_tes_local.yaml"
    if loc.exists():
        out |= set(yaml.safe_load(loc.read_text(encoding="utf-8")).get("name_scan_terms", []))
    if not out:
        raise SystemExit("no local term lists found - cannot scan")
    return sorted(out, key=len, reverse=True)


def scan(files: list[str]) -> list[tuple[str, int, str]]:
    pats = [(t, re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])")) for t in terms()]
    hits = []
    for f in files:
        p = Path(f)
        if p.suffix in {".png", ".parquet", ".zip", ".pdf", ".xlsx"} or not p.is_file():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for t, rx in pats:
                if rx.search(line):
                    hits.append((f, i, t))
    return hits


if __name__ == "__main__":
    h = scan(sys.argv[1:])
    for f, i, t in h:
        print(f"{f}:{i}: real-name term '{t}'")
    print(f"{len(h)} hit(s)")
    sys.exit(1 if h else 0)
