"""Tests for energis.io._output_paths — canonical output directory resolution."""

import os
import warnings

import pytest

from energis.io._output_paths import (
    DASHBOARD_DIR,
    RUNS_DIR,
    WORKFLOWS_DIR,
    resolve_runs_dir,
    resolve_workflows_dir,
)


class TestConstants:
    def test_runs_dir(self):
        assert RUNS_DIR == "outputs/runs"

    def test_workflows_dir(self):
        assert WORKFLOWS_DIR == "outputs/workflows"

    def test_dashboard_dir(self):
        assert DASHBOARD_DIR == "outputs/dashboard"


class TestResolveRunsDir:
    def test_no_legacy_dirs_returns_new_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = resolve_runs_dir()
        assert result == RUNS_DIR

    def test_explicit_path_returned_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = resolve_runs_dir("custom/output")
        assert result == "custom/output"

    def test_explicit_path_no_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resolve_runs_dir("custom/output")
        assert len(w) == 0

    def test_legacy_exports_dir_triggers_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        legacy = tmp_path / "exports"
        legacy.mkdir()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_runs_dir()
        assert result == "exports"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "exports" in str(w[0].message)

    def test_legacy_results_dir_triggers_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "results").mkdir()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_runs_dir()
        assert result == "results"
        assert len(w) == 1


class TestResolveWorkflowsDir:
    def test_no_legacy_dirs_returns_new_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = resolve_workflows_dir()
        assert result == WORKFLOWS_DIR

    def test_explicit_path_returned_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = resolve_workflows_dir("my/workflows")
        assert result == "my/workflows"

    def test_legacy_saved_workflows_dir_triggers_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saved_workflows").mkdir()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolve_workflows_dir()
        assert result == "saved_workflows"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
