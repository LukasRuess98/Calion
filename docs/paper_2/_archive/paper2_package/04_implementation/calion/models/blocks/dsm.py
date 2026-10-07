"""Demand-Side Management (DSM) block for Paper 2.

Models load shifting for flexible consumers using a linearized absolute-value
formulation with a rolling energy-conservation constraint.

Formulation (per DSM consumer):
  δ(t) = δ_pos(t) - δ_neg(t)                  [load shift, MW]
  |δ(t)| = δ_pos(t) + δ_neg(t)                [for objective penalty]
  -δ_max ≤ δ(t) ≤ δ_max                       [power limit]
  Σ_{τ ∈ [t, t+Δt_max-1]} δ(τ) = 0   ∀ t     [rolling energy conservation]
  Q_demand_eff(t) = Q_demand_base(t) + δ(t)   [effective demand]
  δ_pos, δ_neg ≥ 0

The penalty cost term added to the objective:
  C_DSM = c_DSM [€/MWh] * Σ_t (δ_pos(t) + δ_neg(t)) * dt_h
"""

from __future__ import annotations

try:
    import pyomo.environ as pyo
except Exception:
    pyo = None

from ..component import BaseComponent
from ..registry import register_component


@register_component(
    "dsm",
    category="demand",
    description="Demand-side management: load shifting with rolling energy conservation",
)
class DSMBlock(BaseComponent):
    """DSM block for a single flexible consumer node.

    Creates δ_pos(t) and δ_neg(t) variables, rolling window energy conservation
    constraints, and contributes a penalty term to the objective function.

    The effective demand at the node is:
        Q_eff(t) = Q_base(t) + δ_pos(t) - δ_neg(t)

    Args:
        name: Component identifier.
        delta_max_mw: Maximum load shift power [MW] (symmetric bound).
        dt_max_h: Rolling window length for energy conservation [hours].
        c_dsm_eur_per_mwh: Penalty cost per MWh of shifted energy [€/MWh].
        dt_h: Timestep duration [hours], typically 1.0.
        label: Optional display label.
    """

    def __init__(
        self,
        name: str,
        delta_max_mw: float,
        dt_max_h: int,
        c_dsm_eur_per_mwh: float,
        dt_h: float = 1.0,
        *,
        label: str | None = None,
    ):
        super().__init__(name, label)
        self.delta_max_mw = float(delta_max_mw)
        self.dt_max_h = int(dt_max_h)
        self.c_dsm_eur_per_mwh = float(c_dsm_eur_per_mwh)
        self.dt_h = float(dt_h)

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach DSM blocks")

        comp = self.name
        times = sorted(Tset)
        t_first = Tset.first()
        t_last = Tset.last()

        # ── Decision variables ────────────────────────────────────────────────
        # δ_pos: load brought forward (demand increased now)
        # δ_neg: load postponed (demand reduced now)
        setattr(m, f"{comp}_dpos", pyo.Var(
            Tset, domain=pyo.NonNegativeReals,
            bounds=(0.0, self.delta_max_mw),
        ))
        setattr(m, f"{comp}_dneg", pyo.Var(
            Tset, domain=pyo.NonNegativeReals,
            bounds=(0.0, self.delta_max_mw),
        ))

        dpos = getattr(m, f"{comp}_dpos")
        dneg = getattr(m, f"{comp}_dneg")

        # Derived expressions: net shift and absolute shift
        def delta_expr(mm, t):
            return dpos[t] - dneg[t]
        setattr(m, f"{comp}_delta", pyo.Expression(Tset, rule=delta_expr))

        def abs_delta_expr(mm, t):
            return dpos[t] + dneg[t]
        setattr(m, f"{comp}_abs_delta", pyo.Expression(Tset, rule=abs_delta_expr))

        # ── Rolling energy conservation ───────────────────────────────────────
        # For each window starting at t: sum of δ over [t, t + dt_max - 1] = 0
        # At the end of the horizon, shorten the window to avoid indexing past t_last.
        time_list = list(times)
        time_set = set(time_list)

        def rolling_balance(mm, t):
            window = [
                tau for tau in time_list
                if t <= tau < t + self.dt_max_h and tau in time_set
            ]
            if len(window) < self.dt_max_h and t + self.dt_max_h - 1 > t_last:
                return pyo.Constraint.Skip
            return sum(dpos[tau] - dneg[tau] for tau in window) == 0.0

        setattr(m, f"{comp}_rolling", pyo.Constraint(Tset, rule=rolling_balance))

        # ── Penalty cost (added to objective via metadata) ────────────────────
        # Cost = c_DSM * Σ_t (dpos + dneg) * dt_h
        penalty_expr = (
            self.c_dsm_eur_per_mwh
            * self.dt_h
            * sum(dpos[t] + dneg[t] for t in times)
        )
        setattr(m, f"{comp}_penalty_expr", pyo.Expression(rule=lambda mm: penalty_expr))

        return {
            "flows": {},  # DSM does not create heat bus flows directly
            "investment": None,
            "metadata": {
                "dpos": dpos,
                "dneg": dneg,
                "delta_max_mw": self.delta_max_mw,
                "dt_max_h": self.dt_max_h,
                "c_dsm_eur_per_mwh": self.c_dsm_eur_per_mwh,
                "penalty_expr": getattr(m, f"{comp}_penalty_expr"),
            },
            "dpos": dpos,
            "dneg": dneg,
            "penalty_expr": penalty_expr,
        }
