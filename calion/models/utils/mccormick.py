"""McCormick envelope linearization for bilinear products W = scale * x * y."""
import pyomo.environ as pyo


def add_mccormick_constraints(
    model,
    name: str,
    W_var,
    x_var,
    y_var,
    x_lo: float,
    x_hi: float,
    y_lo: float,
    y_hi: float,
    time_set,
    scale: float = 1.0,
):
    """Add 4 McCormick envelope constraints for W ≈ scale * x * y.

    Valid outer approximation: tightest linear relaxation given rectangular bounds.
    No binary variables added. W_var, x_var, y_var must be indexed by time_set.

    Args:
        scale: multiplicative constant (e.g. cp_water so W = m_dot * cp * T).
        x_lo/x_hi: bounds on x (e.g. -m_max, m_max for mass flow).
        y_lo/y_hi: bounds on y (e.g. T_min, T_max for temperature).
    """
    xL, xH, yL, yH = x_lo, x_hi, y_lo, y_hi
    s = scale

    def mc1(m, t):  # W >= xL*y + x*yL - xL*yL  (lower-left corner)
        return W_var[t] >= s * (xL * y_var[t] + x_var[t] * yL - xL * yL)

    def mc2(m, t):  # W >= xH*y + x*yH - xH*yH  (upper-right corner)
        return W_var[t] >= s * (xH * y_var[t] + x_var[t] * yH - xH * yH)

    def mc3(m, t):  # W <= xH*y + x*yL - xH*yL  (upper-left corner)
        return W_var[t] <= s * (xH * y_var[t] + x_var[t] * yL - xH * yL)

    def mc4(m, t):  # W <= xL*y + x*yH - xL*yH  (lower-right corner)
        return W_var[t] <= s * (xL * y_var[t] + x_var[t] * yH - xL * yH)

    setattr(model, f'{name}_mc1', pyo.Constraint(time_set, rule=mc1))
    setattr(model, f'{name}_mc2', pyo.Constraint(time_set, rule=mc2))
    setattr(model, f'{name}_mc3', pyo.Constraint(time_set, rule=mc3))
    setattr(model, f'{name}_mc4', pyo.Constraint(time_set, rule=mc4))
