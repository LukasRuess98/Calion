# Paper Run Report — Auto-generated
# Last updated: 2026-04-27

## Status

| Item | Status | Notes |
|---|---|---|
| Configs L1/L2/L3_MILP/L3_MIQP | DONE | All B1-B8 bugs fixed, harmonized |
| User answers (§10) | DONE | See 00_user_answers.md |
| Config resolution log | DONE | See 00_config_resolution.md |
| CHECK V1 (168h HiGHS) | PASS | L1 91,250 EUR, L3_MILP 91,509 EUR, cost order correct |
| CHECK V1 L3_MIQP | BLOCKED | Gurobi required |
| Schemas (_schemas/*.json) | DONE | All 5 schemas written |
| Tools (tablegen, fill_paper, gen_synth) | DONE | |
| synth_configs/ (36 YAMLs) | DONE | gen_synth.py --seed 42 |
| synth_configs/_README.md | DONE | |
| LaTeX tables (11 files) | SKELETON | Placeholder data — need Gurobi runs |
| Figure F1 (comparison design) | DONE | Real schematic |
| Figure F2 (topology) | DONE | networkx, real pipe data |
| Figure F3 (cost topology) | SKELETON | Placeholder — needs L1/L2/L3 runs |
| Figure F4 (cost extended) | SKELETON | Placeholder — needs L3/L3+/L3NL runs |
| Figure F5 (cost waterfall) | SKELETON | Placeholder — needs L3/L3+ runs |
| Figure F6 (pump pwl vs quad) | SKELETON | Placeholder — needs L3+/L3NL runs |
| Figure F7 (storage winter week) | SKELETON | Placeholder — needs all-level runs |
| Figure F8 (charge hour hist) | SKELETON | Placeholder — needs all-level runs |
| Figure F9 (dispatch heatmap) | SKELETON | Placeholder — needs L3+ run |
| Figure F10 (synth topology gap) | SKELETON | Placeholder — needs 36x L1/L2 runs |
| Figure F11 (synth physics gap) | SKELETON | Placeholder — needs 36x L3/L3+ runs |
| Figure F12 (synth lin error) | SKELETON | Placeholder — needs 36x L3+/L3NL runs |
| Figure F13 (tornado sensitivity) | SKELETON | Placeholder — needs sensitivity runs |
| Figure F14 (solve time) | SKELETON | Placeholder — needs all runs |

## Blocked on Gurobi

Everything below requires `run.solver: gurobi` to be functional:

1. **Annual runs** (§2): L1, L2, L3_MILP (basic), L3_MILP (extended), L3_MIQP — 8760h each
2. **Sensitivity runs** (§4): 4 levels x 7 scenarios = 28 runs
3. **Synthetic runs** (§5): 36 configs x 5 levels = 180 runs
4. **CHECK V1 L3_MIQP**: 168h nonlinear validation
5. **All skeleton figures and tables**: will be filled by tablegen.py / run postprocessors after runs complete

## Definition-of-Done Progress

- [x] §1 hard bugs resolved, configs harmonised
- [ ] All 5 primary runs produce §3 artefacts (BLOCKED: Gurobi)
- [ ] All sensitivity runs complete (BLOCKED: Gurobi)
- [x] Synthetic generation reproducible from `tools/gen_synth.py --seed 42`
- [x] All 14 figures exist in figures/ (F1/F2 real; F3-F14 placeholders)
- [x] All 11 tables exist in tables/ (placeholder data)
- [ ] fill_paper.py --fill writes Paper_filled.tex (BLOCKED: needs run data)
- [ ] Paper_filled.pdf builds clean (BLOCKED)
- [ ] REPORT.md final numbers (this file — BLOCKED)
