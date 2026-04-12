# Formula Reference — Paper Sections 1–3

**Quick lookup for all 38 equations in updated draft**

---

## CONSTRAINT FORMULATION (Eqs. 1–13)

### Heat Pump Constraints
| Eq. | Formula | Meaning |
|-----|---------|---------|
| (1) | $Q_{\text{hp}}[t] = \text{COP}[t] \cdot P_{\text{hp}}[t]$ | HP output (linear via pre-computed COP) |
| (2) | $Q_{\text{hp}}[t] \leq \text{cap}_{\text{hp}}$ | Capacity bound |
| (3) | $\text{cap}_{\min} \leq \text{cap}_{\text{hp}} \leq \text{cap}_{\max}$ | Investment coupling (Big-M) |

### Storage Constraints
| Eq. | Formula | Meaning |
|-----|---------|---------|
| (4) | $E_{\text{tes}}[t] = E_{\text{tes}}[t-1](1-\lambda_{\text{loss}}) + \eta_c Q_c[t] - Q_d[t]/\eta_d - Q_{\text{loss,tes}}[t]$ | State of charge dynamics |
| (5) | $0 \leq E_{\text{tes}}[t] \leq E_{\max}$ | Energy bounds |
| (6) | $Q_c[t], Q_d[t] \leq P_{\max}$ | Power bounds |
| (7) | $Q_c[t] \leq P_{\max} \cdot y_{\text{charge}}[t]$ | Charge control (Big-M) |
| (8) | $Q_d[t] \leq P_{\max} \cdot (1 - y_{\text{charge}}[t])$ | Discharge control (Big-M) |

### Network & Grid Constraints
| Eq. | Formula | Meaning |
|-----|---------|---------|
| (9) | $Q_{\text{loss}}[t] = \frac{U \cdot L}{1000} (T_s - T_{\text{amb}})$ | Physical pipe heat loss (Svendsen et al.) |
| (10) | $Q_{\text{loss}}[t] = 6.5$ MW | Brownfield numerical example |
| (11) | $P_{\text{buy}}[t] \leq M \cdot y_{\text{buy}}[t]$ | Grid import (Big-M) |
| (12) | $P_{\text{sell}}[t] \leq M \cdot (1 - y_{\text{buy}}[t])$ | Grid export (Big-M, mutual exclusivity) |
| (13) | $P_{\text{grid,max}} \geq P_{\text{buy}}[t]$ | Peak tracking (for demand charge) |

---

## OBJECTIVE FUNCTION (Eqs. 14–20)

**Total Cost Minimization:**

| Eq. | Formula | Description |
|-----|---------|-----------|
| (14) | $Z = C_{\text{fuel}} + C_{\text{elec}} + C_{\text{CO}_2} + C_{\text{dump}} + C_{\text{demand}} + C_{\text{invest}}$ | Total annualized cost [€] |
| (15) | $C_{\text{fuel}} = \sum_t \sum_g p_f(g) \cdot F_g[t]$ | Fuel costs |
| (16) | $C_{\text{elec}} = \sum_t [(p_{\text{el}}[t] + c_{\text{fee}}) P_{\text{buy}}[t] - (p_{\text{el}}[t] - c_{\text{spread}}) P_{\text{sell}}[t]]$ | Electricity costs (buy/sell spread) |
| (17) | $C_{\text{CO}_2} = p_{\text{CO}_2} \sum_t [\sum_g \text{ef}_f(g) F_g[t] + \text{ef}_{\text{grid}}[t] P_{\text{buy}}[t]] / 1000$ | CO₂ tracking costs |
| (18) | $C_{\text{dump}} = c_{\text{dump}} \sum_t Q_{\text{dump}}[t]$ | Excess heat penalty |
| (19) | $C_{\text{demand}} = c_{\text{demand}} \cdot P_{\text{grid,max}}$ | Annual peak demand charge |
| (20) | $C_{\text{invest}} = \sum_c [\text{CAPEX}_c \cdot \text{cap}_c + c_{\text{act},c} \cdot y_{\text{build},c}] / L_c$ | Annualized investment costs |

---

## LINEARIZATION STRATEGY #1: TEMPERATURE-DEPENDENT COP (Section 3.3)

| Eq. | Formula | Context |
|-----|---------|---------|
| (21) | $\text{COP}[t] = \eta_{\text{Carnot}} \cdot \frac{T_{\text{sink}}[K]}{T_{\text{sink}}[K] - T_{\text{source}}[t][K]}$ | Carnot-based HP model with efficiency factor |
| (22) | $\varepsilon_{\text{interp}} \lesssim 3.6\%$ | Bilinear interpolation error (5-point grid, 30K range) |
| (23) | $\varepsilon_{\text{COP}} \approx \sqrt{3.6^2 + 2^2} \approx 4.1\%$ | Combined error (interpolation + measurement) |
| (24) | $\Delta Z \approx 0.041 \times 0.35 \times Z_{\text{total}} \approx 1.4\%$ | Impact on total system cost (acceptable) |

**Key**: COP[t] is a **fixed parameter**, not optimization variable → constraint (1) remains **linear** in $P_{\text{hp}}[t]$

---

## LINEARIZATION STRATEGY #2: STORAGE LOSS GEOMETRY (Section 3.4)

| Eq. | Formula | Description |
|-----|---------|-----------|
| (25) | $A_{\text{surface}}(h) = A_{\text{const}} + A_{\text{side}} \cdot h$ | Tank surface area (linear in fill fraction) |
| (26) | $Q_{\text{loss,tes}}[t] = U_{\text{tank}} \cdot A(h[t]) \cdot (T_{\text{hot}} - T_{\text{amb}})$ | Tank heat loss (nonlinear in $E[t]$ via $h$) |
| (27) | $Q_{\text{loss},i} = U_{\text{tank}} \cdot A_i \cdot \Delta T$ | Reference loss at breakpoint $E_i$ |
| (28) | $Q_{\text{loss}}(E) \approx a_i E + b_i$ for $E \in [E_i, E_{i+1}]$ | Piecewise-linear approximation |
| (29) | $a_i = (Q_{\text{loss},i+1} - Q_{\text{loss},i})/(E_{i+1} - E_i)$, $b_i = Q_{\text{loss},i} - a_i E_i$ | Slope & intercept calculation |
| (33) | $\max_E \|Q_{\text{loss}}(E) - Q_{\text{loss,PWL}}(E)\| \leq M (E_{\max}/N)^2$ | Error bound (Theorem 2) |

**Application**: Tank with 500 MWh capacity, N=10 segments → error ≤250W (~1%)

---

## PHYSICAL STATE CONSTRAINTS (Eqs. 34–38)

| Eq. | Formula | Meaning |
|-----|---------|---------|
| (34) | $T_{\text{supply},n}[t] \geq T_{\text{return},n}[t] - \epsilon_T$ | Temperature validity (supply ≥ return) |
| (35) | $p_{\text{supply},n}[t] \geq p_{\min}$ | Minimum supply pressure (cavitation prevention) |
| (36) | $p_{\text{return},n}[t] \geq p_{\min}$ | Minimum return pressure |
| (37) | $v_{\text{pipe},i}[t] \leq v_{\max}$ | Maximum pipe velocity (erosion/noise limit) |
| (38) | $v_{\text{pipe},i}[t] = \dot{m}_i[t] / (\rho_w \cdot A_i)$ | Velocity-flow relationship (linear) |

**Parameters**: $\epsilon_T = 0.1\,$°C, $p_{\min} = 0.5\,$bar, $v_{\max} = 2.5\,$m/s, $\rho_w \approx 983\,$kg/m³

**Note**: Minimum velocity ($v_{\min} = 0.3\,$m/s) is *not* a hard constraint — it conflicts with zero-flow feasibility. Checked post-solve by `NetworkValidator`.

---

## KEY THEOREM REFERENCES

### Theorem 1: COP Pre-Computation Preserves MILP (Appendix A.2.1)
**Statement**: Pre-computed COP[t] makes constraint (1) linear in $P_{\text{hp}}[t]$, preserving MILP tractability.

**Error guarantee**: COP interpolation error ≤4.1% → system cost error ≤1.4% [acceptable for planning]

### Theorem 2: PWL Approximation Error Bound (Appendix A.2.2)
**Statement**: For $C^2$ loss curve with $|f''(E)| \leq M$, PWL with N segments achieves:
$$\|f - f_{\text{PWL}}\|_\infty \leq M (E_{\max}/N)^2$$

**Application**: Eq. (33) → 500 MWh tank, N=10 → error ≤1%

### Theorem 3: Big-M Constraint Exactness (Appendix A.2.3)
**Statement**: Constraints (3), (7–8), (11–12) are exact (zero LP relaxation gap) when M chosen ≥ max variable.

**Implementation**: Equations (3), (7), (8), (11), (12) all use M = 10,000 MW or M = P_{\max}

---

## SUMMARY STATISTICS

| Item | Count |
|------|-------|
| **Equations Numbered** | 38 |
| **Constraints (S1–S3)** | 18 |
| **Cost Components** | 6 |
| **Linearization Methods** | 2 |
| **Theorems Referenced** | 3 |
| **Error Bounds Quantified** | 3 |
| **Big-M Constraints** | 5 |
| **Piecewise-Linear Segments** | 10 (typical) |

---

## USAGE

**Quick Reference**:
1. **Structure**: Read equations in order 1→38 (follows paper section order)
2. **Searchable**: Use `Eq. (N)` notation when citing formulas
3. **Validation**: Each equation checked against `APPENDIX_EQUATIONS_AND_PROOFS.md`
4. **Publication**: All equations numbered per ECaM parenthesis format

**For Reviewers**:
- Linearization proofs: See theorems in Appendix A.2.1–A.2.3
- Error quantification: Equations (22–24) for COP; Equation (33) for PWL
- Implementation details: Algorithms in Appendix A.3–A.4

---

Generated: March 31, 2026  
Last Updated: April 2, 2026 — Added Eqs. 34–38 (physical state constraints)
