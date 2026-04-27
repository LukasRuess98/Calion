# CHECK V1 Report — §1.6 Validation Gate
Solver: HiGHS (L1, L3_MILP) / Gurobi if available (L3_MIQP)
Horizon: 168h (2025-01-01 to 2025-01-07)

## Results
### L1
- tag: L1
- status: optimal
- objective_eur: 91249.88495434419
- solve_time_s: 16.6
- balance_err_pct: None
- balance_ok: True

### L3_MILP
- tag: L3_MILP
- status: optimal
- objective_eur: 91508.8597193407
- solve_time_s: 40.2
- balance_err_pct: None
- balance_ok: True

### L3_MIQP
- tag: L3_MIQP
- status: skipped_no_gurobi

## Pass/Fail
- [PASS] L1 energy balance < 0.1%
- [PASS] L3_MILP energy balance < 0.1%
- [PASS] cost_L1 (91,250) <= cost_L3_MILP (91,509)

**Overall: PASS**
