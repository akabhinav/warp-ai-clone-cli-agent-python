"""Tests for session persistence."""

import os
import tempfile
import json
import pytest

from pyoz.session import SessionManager


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def session_mgr(tmpdir, monkeypatch):
    """Create a session manager with isolated storage."""
    sessions_dir = os.path.join(tmpdir, "sessions")
    monkeypatch.setattr("pyoz.session.SESSIONS_DIR", sessions_dir)
    work_dir = os.path.join(tmpdir, "project")
    os.makedirs(work_dir)
    return SessionManager(work_dir)


SAMPLE_MESSAGES = [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user", "content": "list files"},
    {"role": "assistant", "content": "Here are the files..."},
]

SAMPLE_STATS = {
    "turns": 2,
    "total_tool_calls": 1,
    "input_tokens": 500,
    "output_tokens": 200,
    "estimated_cost": 0.0045,
}


class TestSaveLoad:
    def test_save(self, session_mgr):
        path = session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        assert os.path.isfile(path)

    def test_load(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        data = session_mgr.load()
        assert data is not None
        assert len(data["messages"]) == 4
        assert data["stats"]["turns"] == 2
        assert data["provider"] == "claude"

    def test_load_no_session(self, session_mgr):
        assert session_mgr.load() is None

    def test_has_session(self, session_mgr):
        assert not session_mgr.has_session()
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS)
        assert session_mgr.has_session()

    def test_delete(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS)
        assert session_mgr.delete()
        assert not session_mgr.has_session()
        assert not session_mgr.delete()  # Already deleted


class TestArchive:
    def test_archive_session(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        archive_path = session_mgr.archive()
        assert archive_path is not None
        assert os.path.isfile(archive_path)

    def test_archive_no_session(self, session_mgr):
        assert session_mgr.archive() is None

    def test_list_history(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        session_mgr.archive()
        history = session_mgr.list_history()
        assert len(history) == 1
        assert history[0]["provider"] == "claude"
        assert history[0]["turns"] == 2

    def test_load_from_history_by_index(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        session_mgr.archive()
        data = session_mgr.load_from_history("1")
        assert data is not None
        assert len(data["messages"]) == 4


class TestExport:
    def test_export_markdown(self, session_mgr):
        session_mgr.save(SAMPLE_MESSAGES, SAMPLE_STATS, "claude", "sonnet")
        md = session_mgr.export_markdown()
        assert md is not None
        assert "# PyOz Session" in md
        assert "hello" in md
        assert "How can I help" in md
        assert "Turns" in md

    def test_export_no_session(self, session_mgr):
        assert session_mgr.export_markdown() is None


class TestMultipleWorkspaces:
    def test_separate_sessions(self, tmpdir, monkeypatch):
        sessions_dir = os.path.join(tmpdir, "sessions")
        monkeypatch.setattr("pyoz.session.SESSIONS_DIR", sessions_dir)

        # Two different project dirs
        proj1 = os.path.join(tmpdir, "proj1")
        proj2 = os.path.join(tmpdir, "proj2")
        os.makedirs(proj1)
        os.makedirs(proj2)

        mgr1 = SessionManager(proj1)
        mgr2 = SessionManager(proj2)

        msgs1 = [{"role": "user", "content": "project 1"}]
        msgs2 = [{"role": "user", "content": "project 2"}]

        mgr1.save(msgs1, {"turns": 1})
        mgr2.save(msgs2, {"turns": 1})

        data1 = mgr1.load()
        data2 = mgr2.load()

        assert data1["messages"][0]["content"] == "project 1"
        assert data2["messages"][0]["content"] == "project 2"
