EnerGIS Documentation
=====================

**EnerGIS** is a modular MILP framework for planning and optimizing
industrial district heating networks, built on top of Pyomo.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   api_reference


Quickstart
----------

.. code-block:: python

   from energis import Network

   net = Network(dt_h=1.0, solver="glpk")
   net.add_heat_pump("HP1", capacity_mw=10.0, cop=3.5)
   net.add_storage("TES", energy_mwh=200.0, power_mw=40.0)
   net.set_demand([5.0] * 24)
   net.set_electricity_price([50.0] * 24)

   result = net.optimize()
   print(result.costs)


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
