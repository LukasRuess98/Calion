"""Configuration: base YAML + overrides; scenario codes F[A][B][T]-[E|H]."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

from .. import daten

BASE = Path("configs/central_tes/base.yaml")


def root() -> Path:
    return daten.repo_root()


def _read(p: Path) -> dict:
    """YAML with optional ``extends: <other.yaml>`` (path relative to this file): the other file is the base."""
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    parent = cfg.pop("extends", None)
    return merge(_read((p.parent / parent).resolve()), cfg) if parent else cfg


def load(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    """Configuration file (default: env ``CENTRAL_TES_CONFIG``, else base.yaml) + overrides. ``paths.data_dir`` switches
    the data set (same schema as ``data/dhn_a``, e.g. the synthetic example)."""
    path = path or os.environ.get("CENTRAL_TES_CONFIG")
    p = Path(path) if path else root() / BASE
    if not p.is_absolute():
        p = root() / p
    cfg = _read(p)
    if overrides:
        cfg = merge(cfg, overrides)
    daten.set_daten_dir(cfg.get("paths", {}).get("data_dir"))
    return cfg


def merge(a: dict, b: dict) -> dict:
    """Deep merge (b wins). Keys with dots ('tes.volume_m3') are expanded."""
    out = copy.deepcopy(a)
    for k, v in b.items():
        if "." in k:
            head, rest = k.split(".", 1)
            v = {rest: v}
            k = head
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def local(cfg: dict) -> dict:
    """Local-only configuration (partner files). Empty dict if absent."""
    p = root() / cfg["paths"]["local_config"]
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def parse_code(code: str) -> dict:
    """'F111-H' -> {'A': True, 'B': True, 'TES': True, 'mode': 'H'}; 'F101' -> mode E."""
    base, _, mode = code.partition("-")
    if len(base) != 4 or base[0] != "F" or set(base[1:]) - {"0", "1"}:
        raise ValueError(f"invalid scenario code {code!r}")
    return {"A": base[1] == "1", "B": base[2] == "1", "TES": base[3] == "1", "mode": (mode or "E").upper()}


FACTORIAL = ["F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"]
