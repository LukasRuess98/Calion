API Reference
=============

High-Level API
--------------

.. automodule:: energis.api
   :members:

Network Builder
---------------

.. autoclass:: energis.network.Network
   :members:
   :undoc-members:

.. autoclass:: energis.network.NetworkResult
   :members:

Configuration
-------------

.. automodule:: energis.config
   :members:

.. automodule:: energis.config.merge
   :members: load_and_merge, deep_merge, load_yaml

.. automodule:: energis.config.schema
   :members: validate_config_schema

Workflow Execution
------------------

.. automodule:: energis.run
   :members:

.. autofunction:: energis.run.workflow.run_workflow

Result Containers
-----------------

.. automodule:: energis.models.results
   :members:

.. autoclass:: energis.run.types.ScenarioResult
   :members:

.. autoclass:: energis.run.types.WorkflowResult
   :members:

Component System
----------------

.. automodule:: energis.models.component
   :members: Component, BaseComponent, Flow, BusType

.. automodule:: energis.models.registry
   :members: register_component, ComponentRegistry

Validation
----------

.. automodule:: energis.validation.analytical_benchmarks
   :members:

.. automodule:: energis.validation.validation_report
   :members:
