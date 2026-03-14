"""Tests for workspace manager."""

import os
import tempfile
import json
import pytest

from pyoz.workspace import WorkspaceManager, PYOZ_HOME, _load_workspaces, _save_workspaces


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def workspace_mgr(monkeypatch, tmpdir):
    """Create a workspace manager with isolated config."""
    config_dir = os.path.join(tmpdir, ".pyoz_test")
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, "workspaces.json")
    monkeypatch.setattr("pyoz.workspace.PYOZ_HOME", config_dir)
    monkeypatch.setattr("pyoz.workspace.WORKSPACES_FILE", config_file)
    return WorkspaceManager()


class TestRegister:
    def test_register_workspace(self, workspace_mgr, tmpdir):
        ws = workspace_mgr.register(tmpdir, "test-project")
        assert ws["name"] == "test-project"
        assert ws["path"] == os.path.abspath(tmpdir)

    def test_register_sets_active(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "proj")
        assert workspace_mgr.get_active() == os.path.abspath(tmpdir)

    def test_register_adds_to_recent(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "proj")
        recent = workspace_mgr.list_recent()
        assert len(recent) == 1
        assert recent[0]["name"] == "proj"

    def test_register_missing_dir(self, workspace_mgr):
        with pytest.raises(FileNotFoundError):
            workspace_mgr.register("/nonexistent/path/xyz123")

    def test_register_deduplicates(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "first")
        workspace_mgr.register(tmpdir, "second")
        recent = workspace_mgr.list_recent()
        assert len(recent) == 1
        assert recent[0]["name"] == "second"

    def test_register_auto_names(self, workspace_mgr, tmpdir):
        ws = workspace_mgr.register(tmpdir)
        assert ws["name"] == os.path.basename(tmpdir)


class TestSwitch:
    def test_switch_by_name(self, workspace_mgr, tmpdir):
        d1 = os.path.join(tmpdir, "proj1")
        d2 = os.path.join(tmpdir, "proj2")
        os.makedirs(d1)
        os.makedirs(d2)
        workspace_mgr.register(d1, "proj1")
        workspace_mgr.register(d2, "proj2")
        ws = workspace_mgr.switch("proj1")
        assert ws["name"] == "proj1"

    def test_switch_by_index(self, workspace_mgr, tmpdir):
        d1 = os.path.join(tmpdir, "proj1")
        d2 = os.path.join(tmpdir, "proj2")
        os.makedirs(d1)
        os.makedirs(d2)
        workspace_mgr.register(d1, "proj1")
        workspace_mgr.register(d2, "proj2")
        ws = workspace_mgr.switch("1")  # Most recent = proj2
        assert ws["name"] == "proj2"

    def test_switch_by_path(self, workspace_mgr, tmpdir):
        d1 = os.path.join(tmpdir, "proj1")
        os.makedirs(d1)
        ws = workspace_mgr.switch(d1)
        assert ws["path"] == os.path.abspath(d1)

    def test_switch_not_found(self, workspace_mgr):
        with pytest.raises(ValueError, match="not found"):
            workspace_mgr.switch("nonexistent_project")


class TestRemove:
    def test_remove_by_name(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "proj")
        assert workspace_mgr.remove("proj")
        assert len(workspace_mgr.list_recent()) == 0

    def test_remove_by_index(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "proj")
        assert workspace_mgr.remove("1")
        assert len(workspace_mgr.list_recent()) == 0

    def test_remove_not_found(self, workspace_mgr):
        assert not workspace_mgr.remove("nope")

    def test_remove_clears_active(self, workspace_mgr, tmpdir):
        workspace_mgr.register(tmpdir, "proj")
        workspace_mgr.remove("proj")
        assert workspace_mgr.get_active() is None


class TestSettings:
    def test_set_and_get(self, workspace_mgr, tmpdir):
        workspace_mgr.set_workspace_setting(tmpdir, "provider", "openai")
        settings = workspace_mgr.get_workspace_settings(tmpdir)
        assert settings["provider"] == "openai"

    def test_empty_settings(self, workspace_mgr, tmpdir):
        settings = workspace_mgr.get_workspace_settings(tmpdir)
        assert settings == {}


class TestPersistence:
    def test_survives_reload(self, workspace_mgr, tmpdir, monkeypatch):
        workspace_mgr.register(tmpdir, "persistent")
        # Create a new manager (simulates restart)
        mgr2 = WorkspaceManager()
        recent = mgr2.list_recent()
        assert len(recent) == 1
        assert recent[0]["name"] == "persistent"
