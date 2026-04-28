# README — How to use the three deliverables

You now have three files in this folder:

| File | Purpose |
|---|---|
| `CLAUDE_CODE_TASKS.md` | The end-to-end run / outputs / figures / tables specification. **This is the file you hand to Claude Code.** |
| `EQUATION_VERIFICATION.md` | Equation-by-equation audit checklist. **Hand this to Claude Code as a follow-up task** once the configs are clean. |
| `Paper_draft_v2.tex` | Updated paper draft. New macros (`\result{...}`, `\figref{...}`, `\todo{...}`) plus `\input{...}` directives so generated tables/figures slot in cleanly. The `% INTERNAL TRACKING` block at the top documents every open issue and must be deleted before submission. |

---

## How to run the paper

All configs, synthetic networks, and tooling are already set up.
**Single command to run everything:**

```bash
# All phases — primary runs + sensitivity + synthetic + tables + fill paper
python scripts/paper/run_paper_full.py

# Preview plan without running any solver
python scripts/paper/run_paper_full.py --dry-run

# Skip L3NL if Gurobi is not available
python scripts/paper/run_paper_full.py --skip-nl

# Run specific phases only
python scripts/paper/run_paper_full.py --phases 1          # primary runs only
python scripts/paper/run_paper_full.py --phases 1 2        # primary + sensitivity
python scripts/paper/run_paper_full.py --phases 3          # synthetic runs only
python scripts/paper/run_paper_full.py --phases 4 5        # tables + fill paper
```

### Phase order

| Phase | Script | Output |
|-------|--------|--------|
| 1 | `paper_runner.py` (called internally) | `output/paper_runs/L1/`, `L2/`, `L3/`, `L3plus/`, `L3NL/` |
| 2 | `sensitivity_runner.py` (called internally) | `output/paper_runs/sensitivity/<level>_<scenario>/` |
| 3 | synth loop over `synth_configs/*.yaml` | `output/paper_runs/synth/<id>_<level>/` |
| 4 | `tools/tablegen.py` | `output/paper_runs/tables/*.tex` |
| 5 | `tools/fill_paper.py --auto` | `output/paper_runs/Paper_filled.tex` |

### Gurobi notes

- L1 / L2 / L3 / L3+ work with **HiGHS** (free). Gurobi not required.
- L3NL (`Memmingen_L3_MIQP.yaml`) requires **Gurobi** with `NonConvex=2`.
- Without Gurobi, L3NL runs are skipped automatically and logged in `run_log.json`.

### Restart safety

Phase 3 (synthetic) checks for existing `meta.json` before running — safe to interrupt and resume.
All run results logged to `output/paper_runs/run_log.json`.

---

## Equation audit (separate task)

After runs are done, hand `EQUATION_VERIFICATION.md` to Claude Code in a fresh context:

> "Read EQUATION_VERIFICATION.md and execute it.
>  Generate output/paper_runs/EQUATION_AUDIT.md and ask me to
>  decide every fail or warn row before changing code."

---

## Pre-run questions (already answered)

All §10 questions answered in `output/paper_runs/00_user_answers.md`. No action needed.

---

## Critical issues (resolved) (already documented inside the files)

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

Once `run_paper_full.py` completes all 5 phases:

1. Open `output/paper_runs/Paper_filled.tex`. Search `\placeholder{` — anything remaining needs manual fill.
2. Search `\todo{` — resolve every open issue.
3. Search `% INTERNAL TRACKING — REMOVE BEFORE SUBMISSION` — delete that block.
4. Search `\result{` / `\figref{` — confirm all resolved to real numbers / figures.
5. Journal: **Applied Energy** → `\bibliographystyle{elsarticle-harv}` (already set).

That's the path to a submission-ready draft.
