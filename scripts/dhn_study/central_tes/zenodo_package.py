"""Zenodo package of the central-TES study: code, configuration, synthetic example data and the anonymised documents.

Built from an explicit allow-list. The non-public data set (``data/dhn_a``), raw data, local configuration, name lists,
result time series and price files are never copied: the build stops if any of them would end up in the package, and
it stops on any hit of the real-name scan (``name_scan``, needs the local term lists).

    python -m scripts.dhn_study.central_tes.zenodo_package [--out zenodo_dhn_a_central_tes] [--version 1.0.0]

Output: ``<out>/`` (README.md, CITATION.cff, LICENSE, requirements.txt, NAME_SCAN.txt, MANIFEST.sha256 and the files
below) and ``<out>.zip`` for the upload (Zenodo accepts at most 100 files per record).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
import zipfile
from pathlib import Path

from .. import daten

# Paths relative to the repository root; copied to the same relative path in the package (imports and links stay valid)
CODE = [
    "scripts/dhn_study/__init__.py", "scripts/dhn_study/daten.py", "scripts/dhn_study/netzmodell.py",
    "scripts/dhn_study/hydraulik.py", "scripts/dhn_study/run_netzmodell.py", "scripts/dhn_study/run_analyse.py",
    "scripts/dhn_study/anker.py", "scripts/dhn_study/auslegung.py", "scripts/dhn_study/wetter.py",
    "scripts/dhn_study/gegenrechnung_pandapipes.py",
    "scripts/dhn_study/kalibrierung/[ABC]/*.csv",                   # calibrations used by the study (A, C, B)
    "scripts/dhn_study/central_tes/*.py", "scripts/dhn_study/central_tes/README.md",
    "configs/central_tes/base.yaml", "configs/central_tes/synthetic.yaml",
    "tests/conftest.py", "tests/test_central_tes.py",
]
CODE_EXCLUDE = ["scripts/dhn_study/central_tes/name_scan.py",        # needs the local name lists, repo-internal
                "scripts/dhn_study/central_tes/zenodo_package.py"]   # this builder
DOCS = [
    "docs/dhn_storage_study/central_tes/model_and_deviations.md",   # model, implementation, deviations
    "docs/dhn_storage_study/central_tes/data_requirements.md",      # data inventory, sources, treatment
    "reports/central_tes/hydraulic_calibration.md",                 # calibration and validation (methods)
    "reports/central_tes/literature_check.md",                      # sources of the techno-economic assumptions
    "reports/central_tes/paper_tables.md",                          # all numbers of the paper tables (generated)
    "reports/central_tes/results_v2.md",                            # results with the numbers quoted in the text
]
SYNTH_DIR = "data/synthetic"                                        # regenerated from the fixed seed
# never in the package (checked on every path, before and after copying)
FORBIDDEN = ["data/dhn_a", "data/raw_dhn_a", "data/local", "data/prices", "data/dwd", "configs/local", "reports/local",
             "results/", "lokal_paket", "prompt_local_agent", "README_LOKAL", "anonymisierung", "klar_", "zuordnung_"]
FORBIDDEN_SUFFIX = {".zip", ".xlsx", ".pdf", ".docx", ".lp", ".log"}
# reviewed hits of the name scan that are not real names: generic German words of the term lists, and the authors'
# own affiliation in the citation metadata (only there)
SCAN_OK = {"Daten": None, "Fernwärmenetz": None, "Lastgänge": None, "Import": None, "Fraunhofer": "CITATION.cff"}


def _verboten(rel: str) -> bool:
    return any(f in rel for f in FORBIDDEN) or Path(rel).suffix.lower() in FORBIDDEN_SUFFIX


TEMPLATES = Path(__file__).resolve().parent / "zenodo"            # README.md.in, CITATION.cff.in, requirements.txt


def write_meta(out: Path, root: Path, version: str):
    """README, CITATION.cff (placeholders {version}, {date}), requirements.txt and the repository's LICENSE."""
    rep = {"{version}": version, "{date}": time.strftime("%Y-%m-%d")}
    for name in ("README.md", "CITATION.cff"):
        txt = (TEMPLATES / f"{name}.in").read_text(encoding="utf-8")
        for k, v in rep.items():
            txt = txt.replace(k, v)
        (out / name).write_text(txt, encoding="utf-8")
    shutil.copy2(TEMPLATES / "requirements.txt", out / "requirements.txt")
    shutil.copy2(root / "LICENSE", out / "LICENSE")


def _dateien(root: Path) -> list[str]:
    out = set()
    for pat in CODE + DOCS:
        hits = [p for p in root.glob(pat) if p.is_file() and "__pycache__" not in p.parts]
        if not hits:
            raise SystemExit(f"allow-list entry without a file: {pat}")
        out |= {p.relative_to(root).as_posix() for p in hits}
    return sorted(out - set(CODE_EXCLUDE))


def build(out: Path, version: str) -> dict:
    root = daten.repo_root()
    files = _dateien(root)
    bad = [f for f in files if _verboten(f)]
    if bad:
        raise SystemExit(f"forbidden paths in the allow-list: {bad}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in files:
        (out / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / f, out / f)
    from . import synthetic_data
    synthetic_data.write(out / SYNTH_DIR, 2025, "2025-01-01 00:00", "2025-02-28 23:00")
    write_meta(out, root, version)
    # anonymisation: real-name scan over every text file of the package
    from . import name_scan
    alle = sorted(p for p in out.rglob("*") if p.is_file())
    for p in alle:
        rel = p.relative_to(out).as_posix()
        if _verboten(rel):
            raise SystemExit(f"forbidden file in the package: {rel}")
    hits = name_scan.scan([str(p) for p in alle])
    ok = [h for h in hits if h[2] in SCAN_OK and SCAN_OK[h[2]] in (None, Path(h[0]).relative_to(out).as_posix())]
    hits = [h for h in hits if h not in ok]
    if hits:
        for f, i, _t in hits:
            print(f"real-name hit: {Path(f).relative_to(out)}:{i}", file=sys.stderr)
        raise SystemExit(f"{len(hits)} real-name hit(s) - package not released")
    n_terms = len(name_scan.terms())
    n_text = sum(1 for p in alle if p.suffix not in {".png", ".parquet", ".zip", ".pdf", ".xlsx"})
    (out / "NAME_SCAN.txt").write_text(
        f"Real-name scan of this package ({time.strftime('%Y-%m-%d')}): {n_text} text files scanned against {n_terms} "
        "terms of the local, non-public term lists (real names of city, network, operator, partners, plants, streets, "
        f"consumers and signal labels; word-boundary match). Result: 0 hits of real names. {len(ok)} reviewed hits are not "
        "real names: generic German words contained in the term lists (e.g. 'Daten') and the authors' affiliation in "
        "CITATION.cff.\n"
        "Binary files (Parquet) contain only the synthetic example data generated from a fixed seed.\n", encoding="utf-8")
    # manifest and zip
    alle = sorted(p for p in out.rglob("*") if p.is_file())
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}" for p in alle]
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    alle = sorted(p for p in out.rglob("*") if p.is_file())
    zp = out.with_suffix(".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in alle:
            z.write(p, f"{out.name}/{p.relative_to(out).as_posix()}")
    return {"files": len(alle), "terms": n_terms, "zip": zp, "zip_MB": zp.stat().st_size / 1e6}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="zenodo_dhn_a_central_tes")
    ap.add_argument("--version", default="1.0.0")
    a = ap.parse_args(argv)
    out = Path(a.out)
    r = build(out if out.is_absolute() else daten.repo_root() / out, a.version)
    print(f"{r['files']} files, name scan against {r['terms']} terms: 0 hits -> {r['zip']} ({r['zip_MB']:.1f} MB)")


if __name__ == "__main__":
    main()
