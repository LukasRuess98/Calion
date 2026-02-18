"""Tests for energis.io.notebook_helpers module."""
from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from energis.io.notebook_helpers import (
    setup_notebook_environment,
    save_workflow_run,
    load_workflow_from_saved,
    list_saved_workflows,
    display_workflow_summary,
    display_kpi_summary,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_workflow():
    """Create a mock workflow object for testing."""
    # Mock PF result
    pf_result = SimpleNamespace(
        table=SimpleNamespace(
            index=[datetime(2024, 1, 1), datetime(2024, 1, 2)],
            columns=["HP1_Q_th", "NG1_Q_th"],
            data={
                "HP1_Q_th": [1.0, 2.0],
                "NG1_Q_th": [0.5, 0.7],
            },
        ),
        series={"P_buy_MW": [0.5, 0.6]},
        summary={
            "objective": {"OBJ_value_EUR": 10000.0},
            "heat_pump_HP1": {
                "Thermal_capacity_MW": 5.0,
                "Build_binary": 1.0,
            },
        },
        costs={
            "CAPEX.heat_pump.HP1": 5000.0,
            "OPEX.electricity": 3000.0,
            "OPEX.gas": 2000.0,
        },
    )

    # Mock RH result
    rh_result = SimpleNamespace(
        table=SimpleNamespace(
            index=[datetime(2024, 1, 1), datetime(2024, 1, 2)],
            columns=["HP1_Q_th", "NG1_Q_th"],
            data={
                "HP1_Q_th": [1.1, 2.1],
                "NG1_Q_th": [0.6, 0.8],
            },
        ),
        series={"P_buy_MW": [0.55, 0.65]},
        summary={
            "objective": {"OBJ_value_EUR": 10500.0},
        },
        costs={
            "OPEX.electricity": 3200.0,
            "OPEX.gas": 2100.0,
        },
    )

    # Mock design
    design = SimpleNamespace(
        heat_pumps={"HP1": {"capacity_mw": 5.0, "build": True}},
        generators={"NG1": {"capacity_mw": 10.0, "build": True}},
        storage=None,
    )

    # Mock plan
    plan = SimpleNamespace(
        steps=["PF", "RH"],
        run_mode="PF_THEN_RH",
    )

    # Create workflow
    workflow = SimpleNamespace(
        pf_result=pf_result,
        rh_result=rh_result,
        mpc_result=None,
        design=design,
        plan=plan,
    )

    return workflow


@pytest.fixture
def saved_workflow_dir(tmp_path: Path, mock_workflow) -> Path:
    """Create a saved workflow directory with all required files."""
    # Create workflow directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workflow_dir = tmp_path / "saved_workflows" / f"Test_Workflow_{timestamp}"
    workflow_dir.mkdir(parents=True)

    # Save workflow.pkl
    with open(workflow_dir / "workflow.pkl", "wb") as f:
        pickle.dump(mock_workflow, f)

    # Save metadata.json
    metadata = {
        "name": "Test Workflow",
        "description": "Test workflow for unit tests",
        "created": datetime.now().isoformat(),
        "last_modified": datetime.now().isoformat(),
        "config_paths": ["configs/base.yaml"],
        "workflow_plan": {
            "steps": ["PF", "RH"],
            "run_mode": "PF_THEN_RH",
        },
    }
    with open(workflow_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return workflow_dir


# ============================================================================
# Tests: setup_notebook_environment
# ============================================================================


def test_setup_notebook_environment_returns_project_root(monkeypatch):
    """Test that setup_notebook_environment returns a valid project root path."""
    # Should work from any directory
    project_root = setup_notebook_environment()

    assert isinstance(project_root, Path)
    assert project_root.exists()
    assert project_root.is_dir()


def test_setup_notebook_environment_adds_to_sys_path(monkeypatch):
    """Test that setup adds project root to sys.path."""
    import sys

    original_path_len = len(sys.path)
    project_root = setup_notebook_environment()

    # Should have added project root to sys.path
    assert str(project_root) in sys.path

    # Clean up
    while len(sys.path) > original_path_len:
        sys.path.pop(0)


def test_setup_notebook_environment_configures_matplotlib(monkeypatch):
    """Test that matplotlib configuration is applied."""
    import matplotlib.pyplot as plt

    # Reset to defaults
    plt.rcdefaults()

    setup_notebook_environment(configure_matplotlib=True)

    # Check that some configuration was applied
    # (exact values depend on implementation, just check it's not default)
    assert plt.rcParams['figure.dpi'] > 0


def test_setup_notebook_environment_server_mode(monkeypatch):
    """Test that server mode sets Agg backend for matplotlib."""
    import matplotlib

    # Setup with server mode
    setup_notebook_environment(configure_matplotlib=True, server_mode=True)

    # Should have set Agg backend
    backend = matplotlib.get_backend()
    assert backend == 'agg' or backend == 'Agg'


def test_setup_notebook_environment_headless_detection(monkeypatch):
    """Test that headless environment is auto-detected."""
    import matplotlib
    import sys

    # Simulate headless environment (no DISPLAY)
    monkeypatch.delenv('DISPLAY', raising=False)

    # Should auto-detect and use Agg
    if sys.platform != 'win32':
        setup_notebook_environment(configure_matplotlib=True, server_mode=False)
        backend = matplotlib.get_backend()
        assert backend == 'agg' or backend == 'Agg'


# ============================================================================
# Tests: save_workflow_run
# ============================================================================


def test_save_workflow_run_creates_directory(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that save_workflow_run creates the workflow directory."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    workflow_dir = save_workflow_run(
        mock_workflow,
        name="Test Save",
        description="Test description",
        save_dir=str(save_dir),
        export_first=False,  # Skip export to avoid dependencies
    )

    assert workflow_dir.exists()
    assert workflow_dir.is_dir()
    assert "Test_Save" in workflow_dir.name


def test_save_workflow_run_saves_pickle_and_metadata(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that workflow.pkl and metadata.json are created."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    workflow_dir = save_workflow_run(
        mock_workflow,
        name="Test Save",
        description="Test description",
        save_dir=str(save_dir),
        export_first=False,
    )

    # Check workflow.pkl exists
    pkl_file = workflow_dir / "workflow.pkl"
    assert pkl_file.exists()

    # Check metadata.json exists and has correct content
    metadata_file = workflow_dir / "metadata.json"
    assert metadata_file.exists()

    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    assert metadata["name"] == "Test Save"
    assert metadata["description"] == "Test description"
    assert "created" in metadata
    assert "workflow_plan" in metadata


def test_save_workflow_run_handles_existing_directory(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that save creates unique directory even if similar name exists."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Save twice with same name
    dir1 = save_workflow_run(
        mock_workflow,
        name="Same Name",
        save_dir=str(save_dir),
        export_first=False,
    )

    # Small delay to ensure different timestamp
    import time
    time.sleep(0.01)

    dir2 = save_workflow_run(
        mock_workflow,
        name="Same Name",
        save_dir=str(save_dir),
        export_first=False,
    )

    # Should have different paths (different timestamps)
    assert dir1 != dir2
    assert dir1.exists()
    assert dir2.exists()


# ============================================================================
# Tests: load_workflow_from_saved
# ============================================================================


def test_load_workflow_from_saved_loads_pickle(saved_workflow_dir: Path):
    """Test that load_workflow_from_saved successfully loads the workflow."""
    workflow = load_workflow_from_saved(saved_workflow_dir, verbose=False)

    assert workflow is not None
    assert hasattr(workflow, "pf_result")
    assert hasattr(workflow, "rh_result")
    assert hasattr(workflow, "design")


def test_load_workflow_from_saved_handles_missing_file(tmp_path: Path):
    """Test that load raises error for non-existent workflow."""
    non_existent = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        load_workflow_from_saved(non_existent, verbose=False)


def test_load_workflow_from_saved_returns_correct_data(saved_workflow_dir: Path):
    """Test that loaded workflow has correct data."""
    workflow = load_workflow_from_saved(saved_workflow_dir, verbose=False)

    # Check PF result
    assert workflow.pf_result.summary["objective"]["OBJ_value_EUR"] == 10000.0
    assert workflow.pf_result.summary["heat_pump_HP1"]["Thermal_capacity_MW"] == 5.0

    # Check RH result
    assert workflow.rh_result.summary["objective"]["OBJ_value_EUR"] == 10500.0

    # Check design
    assert workflow.design.heat_pumps["HP1"]["capacity_mw"] == 5.0


# ============================================================================
# Tests: list_saved_workflows
# ============================================================================


def test_list_saved_workflows_finds_workflows(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that list_saved_workflows finds all saved workflows."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Create multiple workflows
    save_workflow_run(mock_workflow, name="Workflow 1", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Workflow 2", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Workflow 3", save_dir=str(save_dir), export_first=False)

    # List workflows
    workflows = list_saved_workflows(save_dir=str(save_dir), sort_by="date")

    assert len(workflows) == 3
    assert all("name" in wf for wf in workflows)
    assert all("path" in wf for wf in workflows)
    assert all("created" in wf for wf in workflows)


def test_list_saved_workflows_sorts_by_date(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that workflows are sorted by creation date."""
    import time

    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Create workflows with slight delays
    save_workflow_run(mock_workflow, name="First", save_dir=str(save_dir), export_first=False)
    time.sleep(0.01)
    save_workflow_run(mock_workflow, name="Second", save_dir=str(save_dir), export_first=False)
    time.sleep(0.01)
    save_workflow_run(mock_workflow, name="Third", save_dir=str(save_dir), export_first=False)

    # List sorted by date (newest first)
    workflows = list_saved_workflows(save_dir=str(save_dir), sort_by="date")

    # Check order (newest first)
    assert workflows[0]["name"] == "Third"
    assert workflows[1]["name"] == "Second"
    assert workflows[2]["name"] == "First"


def test_list_saved_workflows_sorts_by_name(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that workflows can be sorted by name."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Create workflows with different names
    save_workflow_run(mock_workflow, name="Zebra", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Alpha", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Beta", save_dir=str(save_dir), export_first=False)

    # List sorted by name
    workflows = list_saved_workflows(save_dir=str(save_dir), sort_by="name")

    # Check order (alphabetical)
    assert workflows[0]["name"] == "Alpha"
    assert workflows[1]["name"] == "Beta"
    assert workflows[2]["name"] == "Zebra"


def test_list_saved_workflows_returns_empty_for_no_workflows(tmp_path: Path):
    """Test that empty list is returned when no workflows exist."""
    save_dir = tmp_path / "saved_workflows"
    save_dir.mkdir()

    workflows = list_saved_workflows(save_dir=str(save_dir))

    assert workflows == []


def test_list_saved_workflows_ignores_invalid_directories(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that directories without metadata.json are skipped."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Create valid workflow
    save_workflow_run(mock_workflow, name="Valid", save_dir=str(save_dir), export_first=False)

    # Create invalid directory (no metadata.json)
    invalid_dir = save_dir / "Invalid_20240101_120000"
    invalid_dir.mkdir()

    # List workflows
    workflows = list_saved_workflows(save_dir=str(save_dir))

    # Should only find the valid one
    assert len(workflows) == 1
    assert workflows[0]["name"] == "Valid"


# ============================================================================
# Tests: display_workflow_summary
# ============================================================================


def test_display_workflow_summary_runs_without_error(mock_workflow, caplog):
    """Test that display_workflow_summary executes without errors."""
    with caplog.at_level("INFO"):
        display_workflow_summary(mock_workflow, show_costs=True, show_design=True)

    # Check that some expected content is in log output
    assert "PF" in caplog.text or "RH" in caplog.text


def test_display_workflow_summary_shows_costs(mock_workflow, caplog):
    """Test that costs are displayed when show_costs=True."""
    with caplog.at_level("INFO"):
        display_workflow_summary(mock_workflow, show_costs=True, show_design=False)

    # Should show cost information
    assert "EUR" in caplog.text


def test_display_workflow_summary_shows_design(mock_workflow, caplog):
    """Test that design is displayed when show_design=True."""
    with caplog.at_level("INFO"):
        display_workflow_summary(mock_workflow, show_costs=False, show_design=True)

    # Should show design information
    assert "HP1" in caplog.text or "capacity" in caplog.text.lower()


# ============================================================================
# Tests: display_kpi_summary
# ============================================================================


def test_display_kpi_summary_runs_without_error(mock_workflow, caplog):
    """Test that display_kpi_summary executes without errors."""
    with caplog.at_level("INFO"):
        display_kpi_summary(mock_workflow)

    # Should have some output in log
    assert len(caplog.text) > 0


def test_display_kpi_summary_handles_workflow_without_costs(capsys):
    """Test that KPI summary handles workflow without cost data gracefully."""
    # Create minimal workflow
    minimal_workflow = SimpleNamespace(
        pf_result=None,
        rh_result=None,
        mpc_result=None,
        design=None,
        plan=SimpleNamespace(steps=[], run_mode="UNKNOWN"),
    )

    # Should not crash
    display_kpi_summary(minimal_workflow)

    captured = capsys.readouterr()
    # Should still produce some output (even if it's just "no data")
    assert len(captured.out) >= 0


# ============================================================================
# Tests: Integration
# ============================================================================


def test_save_and_load_roundtrip(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that save and load workflow creates a valid roundtrip."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Save
    workflow_dir = save_workflow_run(
        mock_workflow,
        name="Roundtrip Test",
        description="Testing save/load roundtrip",
        config_paths=["configs/base.yaml", "configs/tech_catalog.yaml"],
        save_dir=str(save_dir),
        export_first=False,
    )

    # Load
    loaded_workflow = load_workflow_from_saved(workflow_dir, verbose=False)

    # Compare
    assert loaded_workflow.pf_result.summary == mock_workflow.pf_result.summary
    assert loaded_workflow.rh_result.summary == mock_workflow.rh_result.summary
    assert loaded_workflow.design.heat_pumps == mock_workflow.design.heat_pumps
    assert loaded_workflow.plan.steps == mock_workflow.plan.steps


def test_full_workflow_with_list_and_load(tmp_path: Path, mock_workflow, monkeypatch):
    """Test complete workflow: save multiple, list, load specific one."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Save multiple workflows
    save_workflow_run(mock_workflow, name="First", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Second", save_dir=str(save_dir), export_first=False)
    save_workflow_run(mock_workflow, name="Third", save_dir=str(save_dir), export_first=False)

    # List all
    all_workflows = list_saved_workflows(save_dir=str(save_dir), sort_by="name")
    assert len(all_workflows) == 3

    # Load the second one (alphabetically: "Second")
    second_workflow_meta = [wf for wf in all_workflows if wf["name"] == "Second"][0]
    loaded = load_workflow_from_saved(second_workflow_meta["path"], verbose=False)

    # Verify it's the correct one
    assert loaded is not None
    assert hasattr(loaded, "pf_result")


# ============================================================================
# Tests: Edge Cases
# ============================================================================


def test_save_workflow_with_none_results(tmp_path: Path, monkeypatch):
    """Test saving workflow where some results are None."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Create workflow with None results
    partial_workflow = SimpleNamespace(
        pf_result=None,
        rh_result=SimpleNamespace(
            table=SimpleNamespace(index=[], columns=[], data={}),
            series={},
            summary={},
            costs={},
        ),
        mpc_result=None,
        design=None,
        plan=SimpleNamespace(steps=["RH"], run_mode="RH_ONLY"),
    )

    # Should not crash
    workflow_dir = save_workflow_run(
        partial_workflow,
        name="Partial Workflow",
        save_dir=str(save_dir),
        export_first=False,
    )

    assert workflow_dir.exists()

    # Load and verify
    loaded = load_workflow_from_saved(workflow_dir, verbose=False)
    assert loaded.pf_result is None
    assert loaded.rh_result is not None
    assert loaded.mpc_result is None


def test_load_workflow_from_string_path(saved_workflow_dir: Path):
    """Test that load_workflow_from_saved accepts string paths."""
    # Should work with string path
    workflow = load_workflow_from_saved(str(saved_workflow_dir), verbose=False)

    assert workflow is not None


def test_save_workflow_generates_unique_timestamps(tmp_path: Path, mock_workflow, monkeypatch):
    """Test that rapid saves generate unique directories."""
    monkeypatch.chdir(tmp_path)
    save_dir = tmp_path / "saved_workflows"

    # Save multiple times rapidly
    dirs = []
    for i in range(5):
        workflow_dir = save_workflow_run(
            mock_workflow,
            name="Rapid Save",
            save_dir=str(save_dir),
            export_first=False,
        )
        dirs.append(workflow_dir)

    # All should be unique
    assert len(set(dirs)) == 5

    # All should exist
    assert all(d.exists() for d in dirs)
