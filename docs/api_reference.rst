API Reference
=============

High-Level API
--------------

.. automodule:: calion.api
   :members:

Network Builder
---------------

.. autoclass:: calion.network.Network
   :members:
   :undoc-members:

.. autoclass:: calion.network.NetworkResult
   :members:

Configuration
-------------

.. automodule:: calion.config
   :members:

.. automodule:: calion.config.merge
   :members: load_and_merge, deep_merge, load_yaml

.. automodule:: calion.config.schema
   :members: validate_config_schema

Workflow Execution
------------------

.. automodule:: calion.run
   :members:

.. autofunction:: calion.run.workflow.run_workflow

Result Containers
-----------------

.. automodule:: calion.models.results
   :members:

.. autoclass:: calion.run.types.ScenarioResult
   :members:

.. autoclass:: calion.run.types.WorkflowResult
   :members:

Component System
----------------

.. automodule:: calion.models.component
   :members: Component, BaseComponent, Flow, BusType

.. automodule:: calion.models.registry
   :members: register_component, ComponentRegistry

Validation
----------

.. automodule:: calion.validation.analytical_benchmarks
   :members:

.. automodule:: calion.validation.validation_report
   :members:
