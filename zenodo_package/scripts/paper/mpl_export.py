"""Matplotlib export helpers for Applied Energy style and LaTeX integration."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable


MM_TO_INCH = 1.0 / 25.4
AE_SINGLE_COLUMN_IN = 85.0 * MM_TO_INCH
AE_DOUBLE_COLUMN_IN = 170.0 * MM_TO_INCH
AE_MAX_HEIGHT_IN = 225.0 * MM_TO_INCH

AE_RCPARAMS = {
    # Typography: Applied Energy typically expects ~8-10 pt figure fonts
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.title_fontsize": 7,
    # Lines and axes
    "lines.linewidth": 1.0,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.minor.size": 1.5,
    "ytick.minor.size": 1.5,
    # Layout and render defaults
    "figure.dpi": 150,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    # Grid and spines
    "axes.grid": True,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.4,
    "grid.color": "#cccccc",
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    # Keep unicode minus stable across LaTeX and raster outputs
    "axes.unicode_minus": False,
}

_PGF_READY: bool | None = None
_PGF_TEXSYSTEM: str | None = None
_PGF_WARNED = False


def _find_tex_engine() -> str | None:
    for engine in ("pdflatex", "xelatex", "lualatex"):
        if shutil.which(engine):
            return engine
    return None


def apply_ae_style(mpl_module) -> None:
    """Apply Applied Energy rcParams to the provided matplotlib module."""
    mpl_module.rcParams.update(AE_RCPARAMS)


def _ensure_pgf_ready(mpl_module) -> bool:
    """Register PGF backend and detect LaTeX engine once per process."""
    global _PGF_READY, _PGF_TEXSYSTEM, _PGF_WARNED

    if _PGF_READY is not None:
        return _PGF_READY

    try:
        from matplotlib.backends.backend_pgf import FigureCanvasPgf

        mpl_module.backend_bases.register_backend("pgf", FigureCanvasPgf)
    except Exception:
        _PGF_READY = False
        if not _PGF_WARNED:
            print("  [WARN] Matplotlib PGF backend unavailable; skipping .pgf export.")
            _PGF_WARNED = True
        return False

    tex_engine = _find_tex_engine()
    if tex_engine is None:
        _PGF_READY = False
        if not _PGF_WARNED:
            print("  [WARN] No LaTeX engine found (pdflatex/xelatex/lualatex); skipping .pgf export.")
            _PGF_WARNED = True
        return False

    _PGF_TEXSYSTEM = tex_engine
    _PGF_READY = True
    return True


def save_figure_bundle(
    fig,
    stem_path: Path,
    *,
    formats: Iterable[str] = ("png", "pdf", "pgf"),
    raster_dpi: int = 600,
) -> list[Path]:
    """Save a figure into multiple formats with robust PGF fallback."""
    import matplotlib as mpl

    stem_path = Path(stem_path)
    stem_path.parent.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for fmt in formats:
        fmt_norm = fmt.lower().strip().lstrip(".")
        if not fmt_norm:
            continue

        out_path = stem_path.with_suffix(f".{fmt_norm}")
        if fmt_norm == "pgf":
            if not _ensure_pgf_ready(mpl):
                continue
            try:
                with mpl.rc_context({
                    "pgf.texsystem": _PGF_TEXSYSTEM or "pdflatex",
                    "pgf.rcfonts": False,
                    "text.usetex": True,
                    "font.family": "serif",
                    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                    "pgf.preamble": "\n".join([
                        r"\usepackage[T1]{fontenc}",
                        r"\usepackage[utf8]{inputenc}",
                        r"\usepackage{siunitx}",
                        r"\usepackage{amsmath}",
                    ]),
                }):
                    fig.savefig(out_path, format="pgf", bbox_inches="tight")
                saved.append(out_path)
            except Exception as exc:
                print(f"  [WARN] PGF export failed for {out_path.name}: {exc}")
            continue

        kwargs = {"bbox_inches": "tight", "format": fmt_norm}
        if fmt_norm in {"png", "jpg", "jpeg", "tif", "tiff"}:
            kwargs["dpi"] = raster_dpi
        fig.savefig(out_path, **kwargs)
        saved.append(out_path)

    return saved
