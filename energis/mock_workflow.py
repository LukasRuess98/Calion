"""
Mock workflow helper for dashboard demonstrations.

This module defines the MockWorkflow class that is used by create_mock_simulations.py
and needs to be importable when loading saved workflows.
"""

from energis.run.rolling_horizon import WorkflowPlan


class MockWorkflow:
    """Mock workflow for demonstration purposes.

    This class mimics the structure of a real WorkflowContext but contains
    mock data for testing the dashboard without running actual optimizations.
    """

    def __init__(self, pf_result, design, solver_name='glpk', dt_h=1.0):
        """Initialize mock workflow.

        Parameters
        ----------
        pf_result : ScenarioResult
            Perfect forecast result
        design : DesignData
            Design data (capacities, etc.)
        solver_name : str
            Solver name (default: 'glpk')
        dt_h : float
            Time step in hours (default: 1.0)
        """
        self.plan = WorkflowPlan(steps=['PF', 'RH'], fix_design=False)
        self.pf_result = pf_result
        self.rh_result = None
        self.mpc_result = None
        self.design = design
        self.config = {}
        self.solver_name = solver_name
        self.dt_h = dt_h
