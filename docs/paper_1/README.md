# README — How to use the three deliverables

You now have three files in this folder:

| File | Purpose |
|---|---|
| `CLAUDE_CODE_TASKS.md` | The end-to-end run / outputs / figures / tables specification. **This is the file you hand to Claude Code.** |
| `EQUATION_VERIFICATION.md` | Equation-by-equation audit checklist. **Hand this to Claude Code as a follow-up task** once the configs are clean. |
| `Paper_draft_v2.tex` | Updated paper draft. New macros (`\result{...}`, `\figref{...}`, `\todo{...}`) plus `\input{...}` directives so generated tables/figures slot in cleanly. The `% INTERNAL TRACKING` block at the top documents every open issue and must be deleted before submission. |

---

## Workflow in PowerShell 7

From your repo root:

```powershell
# 1. Drop the deliverables next to your repo
Copy-Item .\downloads\CLAUDE_CODE_TASKS.md       .\CLAUDE_CODE_TASKS.md
Copy-Item .\downloads\EQUATION_VERIFICATION.md  .\EQUATION_VERIFICATION.md
Copy-Item .\downloads\Paper_draft_v2.tex        .\Paper_draft.tex   # overwrites old draft

# 2. Open Claude Code in the repo
claude code

# 3. Inside Claude Code, hand it the brief in two stages.
#    Stage A — config harmonisation + run pipeline:
#       "Read CLAUDE_CODE_TASKS.md and execute it section by section.
#        Stop at every [CHECK] gate and report the result. Do not
#        proceed past §1 until I confirm the user-input questions
#        in §10."
#
#    Stage B — equation audit (after §1 fixes are merged):
#       "Read EQUATION_VERIFICATION.md and execute it.
#        Generate output/paper_runs/EQUATION_AUDIT.md and ask me to
#        decide every ❌ or ⚠️ row before changing code."
```

The two files were intentionally split so you can let Claude Code run the equation audit in a separate context window — equation checking is detail-heavy and benefits from a fresh start.

---

## Things you should answer before Claude Code runs Stage A

`CLAUDE_CODE_TASKS.md` §10 contains nine questions. The **must-answer-now** subset is:

1. HP capacity — 100 MW or 10 MW? (Suspect typo.)
2. Electrode boiler — does the Memmingen site actually have one?
3. Validation data — file path / sheet name?
4. Pipe roughness — 0.5 mm (aged) confirmed?
5. CO₂ price — 1000 €/t as primary?
6. Time horizon — 8760 h confirmed?

Send the answers as a single message to Claude Code; it will write them to `output/paper_runs/00_user_answers.md` and proceed.

---

## Critical issues recap (already documented inside the files)

| Tag | Issue | Where it lives |
|---|---|---|
| B1 | Duplicate `assets:` block in `Memmingen_L3_MIQP.yaml` silently drops CHP+HP+TES | TASKS §1.1 |
| B2 | Gas EF 200 vs 500 kg/MWh inconsistent | TASKS §1.1 |
| B3 | L2 demand fractions sum to 1.17 (17% over-counting) | TASKS §1.1 |
| B4 | `Memmingen_L3.yaml` has no physics — contradicts paper L3 definition | TASKS §1.1 |
| B5–B8 | Solver, roughness, time horizon, grid limits inconsistent | TASKS §1.1 |
| C1 | L3^NL is **not** true ground truth (φ stays PWL) | EQUATION_VERIFICATION cross-cutting check |
| C2 | Primary case has marginal transport delay (only k_p=1 on far end) | TASKS §1, paper internal block |
| C3 | "Pump cost > 2 % of thermal loss" vs "1–5 % of thermal cost" use different denominators | Paper internal block |

Everything above is captured inside the deliverables; this README is just an executive index.

---

## After the runs

Once Claude Code reports `Definition-of-Done` (TASKS §11), do this manually:

1. Open `Paper_draft.tex` and search for `% INTERNAL TRACKING — REMOVE BEFORE SUBMISSION`. Delete the whole block.
2. Search for `\todo{`. Resolve every one.
3. Search for `\placeholder{`. Anything remaining is something `fill_paper.py` could not auto-fill — interpret manually.
4. Search for `\result{` / `\figref{` to confirm everything resolved to a real number / figure.
5. Pick the journal (Applied Energy → author-year style; ECM → numbered) and adjust `\bibliographystyle{}`.

That's the path to a submission-ready draft.
