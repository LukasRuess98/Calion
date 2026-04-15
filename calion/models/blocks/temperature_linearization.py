"""
Temperature Linearization for MILP District Heating Networks

Computes load-dependent supply and return temperatures from a demand timeseries
at model-build time (pure Python, no Pyomo). Returns a plain dict.

Public API:
    build_temperatures(method, lin_cfg, demand_series, peak_demand_mw,
                       nominal_supply_c, nominal_return_c, time_set)
    -> dict[int, tuple[float, float]]  # {t: (T_supply_c, T_return_c)}

Methods:
    "fixed"  — constant nominal temperatures (backward-compatible default)
    "global" — linear interpolation between min/max endpoints using load fraction
    "pwl"    — piecewise-linear interpolation over N breakpoints
"""


def build_temperatures(
    method: str,
    lin_cfg: dict,
    demand_series: dict,
    peak_demand_mw: float,
    nominal_supply_c: float,
    nominal_return_c: float,
    time_set,
) -> dict:
    """
    Compute supply and return temperatures for every timestep.

    Args:
        method:           "fixed" | "global" | "pwl"
        lin_cfg:          Full linearization sub-config dict (contains
                          'global_profile' or 'temperature_profile' sub-keys)
        demand_series:    {t: Q_demand_MW} for all t in time_set
        peak_demand_mw:   Peak (maximum) network demand in MW; used to normalise
                          the load fraction λ[t] = demand[t] / peak_demand_mw
        nominal_supply_c: Fallback / nominal supply temperature (°C)
        nominal_return_c: Fallback / nominal return temperature (°C)
        time_set:         Iterable of timestep indices

    Returns:
        {t: (T_supply_c, T_return_c)} for all t in time_set
    """
    if not method or method == 'fixed':
        return _fixed(nominal_supply_c, nominal_return_c, time_set)
    if method == 'global':
        return _global(
            lin_cfg.get('global_profile', {}),
            demand_series, peak_demand_mw, time_set,
            nominal_supply_c, nominal_return_c,
        )
    if method == 'pwl':
        return _pwl(
            lin_cfg.get('temperature_profile', {}),
            demand_series, peak_demand_mw, time_set,
        )
    raise ValueError(
        f"Unknown temperature linearization method: {method!r}. "
        f"Must be 'fixed', 'global', or 'pwl'."
    )


# ── private helpers ────────────────────────────────────────────────────────

def _fixed(nominal_supply_c: float, nominal_return_c: float, time_set) -> dict:
    """Return constant nominal temperatures for all timesteps."""
    return {t: (float(nominal_supply_c), float(nominal_return_c)) for t in time_set}


def _global(
    cfg: dict,
    demand_series: dict,
    peak_demand_mw: float,
    time_set,
    nominal_supply_c: float,
    nominal_return_c: float,
) -> dict:
    """
    Linear interpolation between two endpoints.

    λ[t] = Q[t] / peak  (clamped to [0, 1])
    T_supply[t] = T_s_min + λ × (T_s_max - T_s_min)
    T_return[t] = T_r_max - λ × (T_r_max - T_r_min)
    """
    T_s_min = float(cfg.get('T_supply_min_c', 70.0))
    T_s_max = float(cfg.get('T_supply_max_c', 95.0))
    T_r_max = float(cfg.get('T_return_max_c', 55.0))
    T_r_min = float(cfg.get('T_return_min_c', 45.0))

    result = {}
    for t in time_set:
        lam = max(0.0, min(1.0, demand_series.get(t, 0.0) / peak_demand_mw))
        T_s = T_s_min + lam * (T_s_max - T_s_min)
        T_r = T_r_max - lam * (T_r_max - T_r_min)
        result[t] = (T_s, T_r)
    return result


def _pwl(cfg: dict, demand_series: dict, peak_demand_mw: float, time_set) -> dict:
    """
    Piecewise-linear interpolation over N breakpoints.

    Config keys (under 'temperature_profile'):
        load_fractions: [f_0, ..., f_N]  strictly increasing, f_0>=0, f_N<=1
        T_supply_c:     [s_0, ..., s_N]  supply temps at each breakpoint
        T_return_c:     [r_0, ..., r_N]  return temps at each breakpoint

    Validates: T_supply[i] > T_return[i] for all i.
    """
    load_fracs = cfg.get('load_fractions')
    T_supply_pts = cfg.get('T_supply_c')
    T_return_pts = cfg.get('T_return_c')

    if load_fracs is None or T_supply_pts is None or T_return_pts is None:
        raise ValueError(
            "PWL method requires config key 'temperature_profile' with "
            "'load_fractions', 'T_supply_c', and 'T_return_c' lists."
        )
    n = len(load_fracs)
    if len(T_supply_pts) != n or len(T_return_pts) != n:
        raise ValueError(
            "PWL breakpoints: load_fractions, T_supply_c, T_return_c must "
            "all have the same length."
        )
    if load_fracs[0] < 0.0 or load_fracs[-1] > 1.0:
        raise ValueError(
            f"PWL load_fractions must lie within [0, 1]. "
            f"Got first={load_fracs[0]}, last={load_fracs[-1]}."
        )
    for i in range(n - 1):
        if load_fracs[i] >= load_fracs[i + 1]:
            raise ValueError(
                f"PWL load_fractions must be strictly increasing. "
                f"Violation at index {i}: {load_fracs[i]} >= {load_fracs[i+1]}."
            )
    for i in range(n):
        if T_supply_pts[i] <= T_return_pts[i]:
            raise ValueError(
                f"PWL breakpoint {i}: T_supply ({T_supply_pts[i]}) must be "
                f"> T_return ({T_return_pts[i]})."
            )

    result = {}
    for t in time_set:
        lam = max(0.0, min(1.0, demand_series.get(t, 0.0) / peak_demand_mw))
        T_s = _interpolate(lam, load_fracs, T_supply_pts)
        T_r = _interpolate(lam, load_fracs, T_return_pts)
        result[t] = (T_s, T_r)
    return result


def _interpolate(x: float, xs: list, ys: list) -> float:
    """
    Linear interpolation. x is clamped to [xs[0], xs[-1]].
    No numpy required — operates on plain Python lists.
    """
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return float(ys[i]) + t * (float(ys[i + 1]) - float(ys[i]))
    return float(ys[-1])
