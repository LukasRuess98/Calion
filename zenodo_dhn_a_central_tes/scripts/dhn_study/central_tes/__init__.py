"""Central TES with two industrial heat sources at site S of DHN-A: MILP (HiGHS), hydraulic coupling, study runs.

Modules
-------
* ``config``      – YAML configuration with overrides (scenario codes, sensitivities)
* ``inputs``      – hourly inputs 2025: demand, temperatures, prices, partner-A availability (local file), grid CO2
* ``cop``         – Carnot-fraction COP time series per HP mode, cascade ratio, lift flags
* ``milp``        – the energy-layer MILP (Pyomo, solved with HiGHS)
* ``hydraulics``  – evaluation of a schedule on the calibrated meshed Ersatznetz, limits, pump curves
* ``coupling``    – Mode E (post-hoc validation) and Mode H (hydraulic-envelope iteration)
* ``metrics``     – annual metrics, Shapley attribution, break-even values
* ``rolling``     – rolling-horizon operation with forecast errors
* ``run``         – CLI entry point
"""
