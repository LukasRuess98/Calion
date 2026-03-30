Quickstart Guide
================

Installation
------------

.. code-block:: bash

   pip install -e ".[solver]"

This installs EnerGIS with Pyomo. You will also need a solver such as
`GLPK <https://www.gnu.org/software/glpk/>`_ or
`CBC <https://github.com/coin-or/Cbc>`_.

Programmatic Usage (Network API)
---------------------------------

The ``Network`` class provides a PyPSA-inspired interface for building
and solving optimisation models entirely from Python:

.. code-block:: python

   from energis import Network

   # 1. Create a network with hourly resolution
   net = Network(dt_h=1.0, solver="glpk")

   # 2. Add components
   net.add_heat_pump("HP1", capacity_mw=10.0, cop=3.5)
   net.add_heat_pump("HP2", capacity_mw=5.0, cop=4.0)
   net.add_storage("TES", energy_mwh=200.0, power_mw=40.0, eta_charge=0.95)
   net.add_generator("Boiler", cap_th_mw=20.0, efficiency=0.90)

   # 3. Set time series (24 hours)
   net.set_demand([8.0, 7.5, 7.0, 6.5, 6.0, 7.0, 9.0, 12.0,
                    14.0, 13.0, 12.0, 11.0, 10.0, 9.5, 10.0, 11.0,
                    13.0, 14.0, 13.0, 11.0, 9.0, 8.0, 7.5, 7.0])
   net.set_electricity_price([40.0] * 8 + [80.0] * 8 + [40.0] * 8)

   # 4. Solve
   result = net.optimize()

   # 5. Inspect results
   print(f"Total cost: {result.total_cost():.2f} EUR")
   print(f"Solver status: {'optimal' if result.is_optimal else 'check'}")

YAML-Based Usage
-----------------

For more complex setups, use YAML configuration files:

.. code-block:: python

   from energis.api import load_config, run_workflow

   cfg = load_config(["configs/base.yaml", "configs/scenario.yaml"])
   result = run_workflow(["configs/base.yaml", "configs/scenario.yaml"])

   if result.pf_result:
       print(result.pf_result.costs)

CLI Usage
---------

.. code-block:: bash

   # Run a scenario from config files
   python -m energis configs/base.yaml configs/scenario.yaml

   # Or using the installed entry point
   energis configs/base.yaml configs/scenario.yaml
