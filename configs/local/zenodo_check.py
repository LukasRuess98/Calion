"""LOCAL ONLY: checks of the Zenodo package — real-name scan of every file (text, file names, CSV headers, parquet
columns and string values, PDF text and metadata), PDF metadata listing, tests on the synthetic example, file tree."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.dhn_study.central_tes.name_scan import terms  # noqa: E402

TEXT = {".py", ".md", ".yaml", ".yml", ".csv", ".json", ".txt", ".cff", ".toml", ""}


def texts(f: Path) -> list[tuple[str, str]]:
    out = [("file name", str(f))]
    if f.suffix in TEXT or f.name in ("LICENSE", ".zenodo.json"):
        out.append(("content", f.read_text(encoding="utf-8", errors="replace")))
    elif f.suffix == ".pdf":
        out.append(("pdf text", subprocess.run(["pdftotext", str(f), "-"], capture_output=True, text=True).stdout))
        out.append(("pdf info", subprocess.run(["pdfinfo", "-meta", str(f)], capture_output=True, text=True).stdout))
    elif f.suffix == ".parquet":
        d = pd.read_parquet(f)
        s = " ".join(map(str, d.columns)) + " " + " ".join(map(str, d.index.names))
        for c in d.select_dtypes(include="object"):
            s += " " + " ".join(map(str, d[c].unique()[:10000]))
        import pyarrow.parquet as pq
        s += " " + str(pq.read_schema(f).metadata)
        out.append(("parquet", s))
    else:
        out.append(("binary strings", subprocess.run(["strings", str(f)], capture_output=True, text=True).stdout))
    return out


def scan(pkg: Path) -> list[tuple]:
    pats = [(t, re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])")) for t in terms()]
    hits = []
    for f in sorted(p for p in pkg.rglob("*") if p.is_file()):
        for kind, s in texts(f):
            if kind == "file name":
                s = str(f.relative_to(pkg))
            for t, p in pats:
                for m in p.finditer(s):
                    line = s.count("\n", 0, m.start()) + 1
                    hits.append((str(f.relative_to(pkg)), kind, line, t))
    return hits


if __name__ == "__main__":
    pkg = Path(sys.argv[1])
    h = scan(pkg)
    print(f"{len(h)} hit(s)")
    for x in h:
        print("  ", x)
