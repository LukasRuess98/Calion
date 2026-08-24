# Markup and clean builds

Both PDFs come from **one** source file. The failure mode worth designing against is a
marked-up copy that disagrees with the clean one — worse than submitting no markup at all.

## Toggle

```latex
\usepackage{xcolor}
\newif\ifmarkup \markuptrue          % \markupfalse for the clean build
\ifmarkup
  \newcommand{\new}[1]{\textcolor[HTML]{1A5FB4}{#1}}   % new in this revision
  \newcommand{\chg}[1]{\textcolor[HTML]{0F7A5A}{#1}}   % v1 text, materially rewritten
  \newcommand{\gone}[1]{\textcolor[HTML]{9A9996}{[removed: #1]}}
\else
  \newcommand{\new}[1]{#1}
  \newcommand{\chg}[1]{#1}
  \newcommand{\gone}[1]{}
\fi
```

```
pdflatex → bibtex → pdflatex ×2   →  paper_MARKUP.pdf
set \markupfalse, rebuild         →  paper_CLEAN.pdf
```

## Granularity

**Paragraph, not sentence.** The revision rewrote most of the manuscript; sentence-level
colouring would produce confetti and tell the editor nothing.

| Content | Macro |
|---|---|
| The fifteen merged section files | `\new` |
| The four new subsections — cost accounting, zone clustering, fidelity vs cost, physics nulls | `\new` |
| Sections transcribing v1 with level names remapped | `\chg` |
| Numbers that moved with the 135-net grid | `\chg` |
| Three specific removals | `\gone` |

## The three deletions worth flagging

Everything else that vanished was rewritten, and `\chg` already says so. These three are
removals a reviewer could otherwise read as evasion:

1. v1's BCM cross-check — the ×1.330 trunk multiplier, removed because that calibration is
   what R2.4 objected to.
2. v1's limitation conceding that linearisation and transport delay could not be separated
   — removed because the revision separates them.
3. v1's physics-scope mapping table — removed per R2.5's taxonomy-consistency request.

## Legend

In the markup build only, under the title:

```latex
\ifmarkup
\begin{center}\footnotesize\fbox{\parbox{0.9\linewidth}{%
\textbf{Marked-up copy.} \textcolor[HTML]{1A5FB4}{Blue} marks material new in this
revision; \textcolor[HTML]{0F7A5A}{green} marks text carried from the original submission
and materially rewritten; \textcolor[HTML]{9A9996}{grey} marks deletions we judged a reader
would want flagged. Unmarked text is unchanged. Because the manuscript was restructured and
the model levels renamed, marking is at paragraph rather than sentence granularity.}}
\end{center}
\fi
```

That last sentence pre-empts the obvious objection — that the markup is coarse — by giving
the reason before the editor forms it.
